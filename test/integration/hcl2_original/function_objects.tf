variable "object" {
  type = object({
    key   = string
    value = string
  })
}

variable "nested" {
  type = map(object({
    name    = string
    enabled = bool
  }))
}

variable "multi_arg" {
  default = merge({
    a = 1
    b = 2
  }, {
    c = 3
  })
}
