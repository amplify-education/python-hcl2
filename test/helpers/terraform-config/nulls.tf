terraform = {
  unary = !null
  binary = (a == null)
  tuple = [null, 1, 2]
  single = null
  conditional = null ? null : null

}
