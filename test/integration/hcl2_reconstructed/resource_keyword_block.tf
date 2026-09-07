data "snowflake_schemas" "in" {
  in {
    database = "database"
  }
}


resource "custom_provider_resource" "resource_name" {
  if {
    name = "if_block"
  }
  

  for {
    name = "for_block"
  }
  

  for_each {
    name = "for_each_block"
  }
  

  else {
    name = "else_block"
  }
  

  endif {
    name = "endif_block"
  }
  

  endfor {
    name = "endfor_block"
  }
  

  true {
    name = "true_block"
  }
  

  false {
    name = "false_block"
  }
  

  null {
    name = "null_block"
  }
}


in "quoted_label" {
  attribute = "value"
}


block in {
  attribute = "value"
}
