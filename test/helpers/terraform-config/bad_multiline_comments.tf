resource "databricks_user" "user" {
  user_name    = var.databricks_username
  display_name = "var.databricks_display_name /*
  allow_cluster_create = var.allow_cluster_create */
}
