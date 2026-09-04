resource "custom_provider_resource" "resource_name" {
  name = "resource_name"
  
  if {
    value = "block_value1"
  }
  

  in {
    value = "block_value2"
  }
  

  for {
    value = "block_value3"
  }
  

  for_each {
    value = "block_value4"
  }
  

  true {
    value = "block_value5"
  }
}


resource in {
  value = "keyword_label_value"
}


in "labeled_block" {
  value = "top_level_value"
}
