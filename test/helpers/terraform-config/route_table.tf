resource "aws_route" "tgw" {
  count = (
    var.tgw_name == "" ?
    0 :
    var.number_of_az
  )

  route_table_id         = aws_route_table.rt[count.index].id
  destination_cidr_block = "10.0.0.0/8"
  transit_gateway_id     = data.aws_ec2_transit_gateway.tgw[0].id
}

resource "aws_route" "tgw-dot-index" {
  count                  = var.tgw_name == "" ? 0 : var.number_of_az
  route_table_id         = aws_route_table.rt[count.index].id
  destination_cidr_block = "10.0.0.0/8"
  transit_gateway_id     = data.aws_ec2_transit_gateway.tgw.0.id
}
