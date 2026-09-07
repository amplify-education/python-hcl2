resource "aws_api_gateway_rest_api" "example" {
  body = jsonencode({
    security_definitions = {
      sigv4 = {
        type                         = "apiKey"
        name                         = "Authorization"
        in                           = "header"
        x-amazon-apigateway-authtype = "awsSigv4"
      }
    }
  })
}

keywords_in_every_position = {
  leading  = 0
  if       = 1
  in       = 2
  for      = 3
  for_each = 4
  else     = 5
  endif    = 6
  endfor   = 7
  true     = 8
  false    = 9
  null     = 10
  trailing = 11
}

colon_separated = {
  a : 0,
  in : "header"
}
