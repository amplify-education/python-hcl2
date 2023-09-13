locals {
  nested_interpolation = "tags: ${join(";", ["names:${join(",", ["name:${example}"])}"])}"
}
