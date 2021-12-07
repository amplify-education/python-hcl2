resource "databricks_user" "user" {
  user_name    = var.databricks_username
  /* an actual multi-line comment
  and now it is closed, so this better fail vvv */
  display_name = "var.databricks_display_name
  allow_cluster_create = var.allow_cluster_create
}
