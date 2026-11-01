declare double @__nv_sin(double)
define void @test_kernel(ptr %out, double %x) {
  %v = call double @__nv_sin(double %x)
  store double %v, ptr %out
  ret void
}
!llvm.module.flags = !{!0}
!0 = !{i32 1, !"wchar_size", i32 4}
