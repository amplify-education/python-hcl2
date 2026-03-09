resource aws_instance web {
  ami           = "ami-12345"
  instance_type = "t2.micro"
  count         = 2
}


resource aws_s3_bucket data {
  bucket = "my-bucket"
  acl    = "private"
}


resource aws_instance nested {
  ami = "ami-99999"
  
  provisioner local-exec {
    command = "echo hello"
  }
  

  provisioner remote-exec {
    inline = ["puppet apply"]
  }
}


variable instance_type {
  default     = "t2.micro"
  description = "The instance type"
}


locals {
  port    = 8080
  enabled = true
  name    = "my-app"
}
