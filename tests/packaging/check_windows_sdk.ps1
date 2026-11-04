param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot '../../build-windows-sdk'),
    [switch]$BlockBuildNetwork
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
$sdkRecipe = Join-Path $repoRoot 'recipes/adaptivecpp-llvm'
$sdkProfile = Join-Path $sdkRecipe 'profiles/windows-x64-clang19'
$sdkReference = 'adaptivecpp-llvm/25.10.0-llvm19.1.7'
$sdkBuild = Join-Path $OutputDirectory 'build/llvm-sdk/Release'
$artifactDirectory = Join-Path $OutputDirectory 'artifacts'
New-Item -ItemType Directory -Force $artifactDirectory | Out-Null

function Invoke-Native {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable exited with status $LASTEXITCODE"
    }
}

# Acquire source before disabling build tools' outbound access. CMake has no
# source acquisition role. All package resolution is explicitly local.
Invoke-Native conan -Arguments @('source', $sdkRecipe)
$conanProfileArguments = @('-pr:h', $sdkProfile, '-pr:b', $sdkProfile, '--no-remote')
$firewallRules = @()
try {
    if ($BlockBuildNetwork) {
        $programs = @('cmake.exe', 'ninja.exe', 'git.exe', 'curl.exe', 'python.exe',
                      'conan.exe', 'powershell.exe', 'pwsh.exe')
        foreach ($program in $programs) {
            $command = Get-Command $program -ErrorAction SilentlyContinue
            if ($command -and $command.Source.EndsWith('.exe')) {
                $ruleName = "AdaptiveCppSDK-Offline-$PID-$($firewallRules.Count)"
                New-NetFirewallRule -Name $ruleName -DisplayName $ruleName `
                    -Direction Outbound -Action Block -Program $command.Source | Out-Null
                $firewallRules += $ruleName
            }
        }
    }
    Invoke-Native conan -Arguments (@('install', $sdkRecipe, '-of', $OutputDirectory) + $conanProfileArguments)
    Invoke-Native conan -Arguments (@('build', $sdkRecipe, '-of', $OutputDirectory) + $conanProfileArguments)
    Invoke-Native conan -Arguments (@('export-pkg', $sdkRecipe, '-of', $OutputDirectory) + $conanProfileArguments)

    Invoke-Native cpack -Arguments @('--config', (Join-Path $sdkBuild 'installer/CPackConfig.cmake'),
                         '-G', 'NSIS', '-B', $artifactDirectory)
    Invoke-Native cpack -Arguments @('--config', (Join-Path $sdkBuild 'installer/CPackConfig.cmake'),
                         '-G', 'ZIP', '-B', $artifactDirectory)
    Invoke-Native conan -Arguments @('cache', 'save', "${sdkReference}:*", '--file',
                         (Join-Path $artifactDirectory 'adaptivecpp-windows-conan.tgz'))

    # Install away from the build/cache, under a path containing spaces. The
    # silent installer runs synchronously; PATH changes do not affect this shell.
    $sdkInstaller = @(Get-ChildItem $artifactDirectory -Filter '*.exe')
    if ($sdkInstaller.Count -ne 1) { throw 'Expected exactly one NSIS installer' }
    $installedSDK = Join-Path $env:ProgramFiles "AdaptiveCpp SDK Validation $PID"
    $installProcess = Start-Process -FilePath $sdkInstaller[0].FullName `
        -ArgumentList @('/S', "/D=$installedSDK") -Wait -PassThru
    if ($installProcess.ExitCode -ne 0) { throw 'NSIS installation failed' }

    $previousPath = $env:PATH
    $previousAppDB = $env:ACPP_APPDB_DIR
    $previousOmpThreads = $env:OMP_NUM_THREADS
    try {
        $env:PATH = "$installedSDK/bin;$env:PATH"
        $env:ACPP_APPDB_DIR = Join-Path $OutputDirectory 'installer-appdb'
        $env:OMP_NUM_THREADS = '2'
        Invoke-Native (Join-Path $installedSDK 'bin/acpp.cmd') -Arguments @('--version')

        $installedConsumer = Join-Path $OutputDirectory 'installed consumer'
        $consumerSource = Join-Path $sdkRecipe 'test_package'
        Invoke-Native cmake -Arguments @('-S', $consumerSource, '-B', $installedConsumer, '-G', 'Ninja',
                             '-DCMAKE_BUILD_TYPE=Release', "-DCMAKE_PREFIX_PATH=$installedSDK",
                             "-DCMAKE_CXX_COMPILER=$installedSDK/bin/clang.exe")
        Invoke-Native cmake -Arguments @('--build', $installedConsumer, '--parallel', '2')
        Invoke-Native (Join-Path $installedConsumer 'sdk_test.exe') -Arguments @()
        $installedOmp = Join-Path $installedConsumer 'sdk_test_omp.exe'
        Invoke-Native (Join-Path $installedSDK 'bin/acpp.cmd') -Arguments @('--acpp-targets=omp', '-O2',
                     (Join-Path $consumerSource 'main.cpp'), '-o', $installedOmp)
        Invoke-Native $installedOmp -Arguments @()
    }
    finally {
        $env:PATH = $previousPath
        $env:ACPP_APPDB_DIR = $previousAppDB
        $env:OMP_NUM_THREADS = $previousOmpThreads
        $uninstaller = Join-Path $installedSDK 'Uninstall.exe'
        if (Test-Path $uninstaller) {
            $uninstallProcess = Start-Process $uninstaller -ArgumentList '/S' -Wait -PassThru
            if ($uninstallProcess.ExitCode -ne 0) { throw 'NSIS uninstall failed' }
        }
    }
}
finally {
    foreach ($ruleName in $firewallRules) {
        Remove-NetFirewallRule -Name $ruleName -ErrorAction Continue
    }
}
