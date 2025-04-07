block {
  a = 1
}

block "label" {
  b = 2
  nested_block_1 "a" {
    foo = "bar"
  }

  nested_block_1 "a" "b" {
    bar = "foo"
  }

  nested_block_1 {
    foobar = "barfoo"
  }

  nested_block_2 {
    barfoo = "foobar"
  }
}
