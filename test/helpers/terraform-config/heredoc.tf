a {
	a = <<EOF
	abc
	def
	EOF
}
b {
	b = <<-EOF
	abcEOFdef
	123
	EOF
}

c {
	c = <<EOF
	abcEOFdef
	123 EOF 456
	EOF
}
