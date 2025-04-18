locals {
  simple_float = 123.456
  small_float = 0.123
  large_float = 9876543.21
  negative_float = -42.5
  negative_small = -0.001
  scientific_positive = 1.23e5
  scientific_negative = 9.87e-3
  scientific_large = 6.022e+23
  integer_as_float = 100.0
  float_calculation = 105e+2 * 3.0 / 2.1
  float_comparison = 5e1 > 2.3 ? 1.0 : 0.0
  float_list = [1.1, 2.2, 3.3, -4.4, 5.5e2]
  float_object = {
    pi = 3.14159
    euler = 2.71828
    sqrt2 = 1.41421
    scientific = -123e+2
  }
}
