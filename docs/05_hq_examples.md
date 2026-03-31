# hq Examples — Real-World Queries

Validated queries against a production Terraform code. All examples use structural mode.

For query syntax reference, see [04_hq.md](04_hq.md).

______________________________________________________________________

## Quick Reference

```sh
hq 'resource[*]' main.tf --json              # Query a file
hq 'resource[*]' infra/ --ndjson             # Query a directory (recursive)
hq 'resource[*]' main.tf vars.tf --json      # Multiple files
hq 'resource[*]' 'modules/**/*.tf' --json    # Glob pattern
hq 'resource[*]' infra/ --json --with-location  # With line numbers
hq 'locals.app_name?' dir/ --value           # Exit 0 even if missing
```

______________________________________________________________________

## Discovery & Inventory

### List all resources

```sh
hq 'resource[*] | .name_labels' infra/ --value --no-filename
```

```
['aws_instance', 'web_server']
['aws_security_group', 'allow_https']
['aws_iam_role', 'lambda_exec']
```

### List resources of a specific type

```sh
hq 'resource.aws_s3_bucket[*] | .name_labels' infra/ --value
```

### List all modules and their sources

```sh
hq 'module~[*] | .source | .value' infra/ --value
```

The `~` skips remaining labels (module names) and descends into all named module blocks. `.source | .value` unwraps the attribute.

```
infra/prod/api/main.tf:"../../modules/ecs_service/v2"
infra/prod/api/main.tf:"../../modules/alb/v1"
```

### List module outputs

```sh
hq 'output[*] | .name_labels' modules/ecs_service/v2/ --value --no-filename
```

### Count resources (blast radius)

```sh
hq 'resource[*] | .name_labels' infra/prod/ --value --no-filename | wc -l
```

______________________________________________________________________

## Tags & Compliance

### Find resources without tags

```sh
hq 'resource~[select(not .tags)] | .name_labels' infra/ --value
```

Non-empty output = potential compliance violation.

### Check if a required local exists

```sh
# Script validation: exit 1 if missing
hq 'locals.app_name' infra/prod/new-service/ --value

# Soft check: exit 0 either way
hq 'locals.app_name?' infra/prod/new-service/ --value
```

______________________________________________________________________

## Multi-Attribute Extraction

Object construction extracts multiple fields per result in one query.

### Instance types for cost analysis

```sh
hq 'resource.aws_instance~[*] | {name: .name_labels, type: .instance_type}' infra/ --ndjson
```

```json
{"__file__": "infra/prod/bastion/ec2.tf", "name": ["aws_instance", "bastion"], "type": "\"t3.small\""}
```

### CPU and memory for ECS services

```sh
hq 'module~[select(.cpu)] | {cpu, memory}' infra/ --ndjson
```

```json
{"__file__": "infra/prod/api/ecs.tf", "cpu": 1024, "memory": 2048}
{"__file__": "infra/prod/worker/ecs.tf", "cpu": 2048, "memory": 4096}
```

### Resource inventory with tags

```sh
hq 'resource~[*] | {type: .name_labels, tags}' infra/prod/ --ndjson
```

______________________________________________________________________

## Deployment & Scaling

### Modules with a specific attribute

```sh
hq 'module~[select(.auto_deploy)] | .auto_deploy | .value' infra/ --value
```

### Resources using for_each or count

```sh
hq 'resource~[select(.for_each)] | .name_labels' infra/ --value
hq 'resource~[select(.count)] | .count | .value' infra/ --value
```

______________________________________________________________________

## Secrets & Parameters

### List SSM parameter paths

```sh
hq 'resource.aws_ssm_parameter~[*] | .name | .value' infra/ --value
```

```
infra/prod/api/ssm.tf:"/${var.region}/${var.env}/api/db-password"
```

### Secrets passed to modules

```sh
hq 'module~[select(.secrets)] | .secrets' infra/ --ndjson
```

______________________________________________________________________

## Provider & Module Versions

### Provider version pins

```sh
hq 'terraform.required_providers' infra/ --ndjson
```

```json
{"__file__": "infra/prod/api/versions.tf", "aws": {"source": "\"hashicorp/aws\"", "version": "\"5.80.0\""}}
```

### Find modules on a specific version

```sh
hq 'module~[*] | {source}' infra/ --ndjson | grep 'ecs_service/v1'
```

______________________________________________________________________

## IAM & Networking

```sh
hq 'data.aws_iam_policy_document[*] | .name_labels' infra/ --value
hq 'resource.aws_iam_role[*] | .name_labels' infra/ --value
hq 'resource.aws_route53_record[*] | .name_labels' infra/ --value
```

______________________________________________________________________

## Non-AWS and Non-Terraform

`hq` parses any HCL2 file — not just `.tf`.

```sh
hq 'resource.datadog_monitor[*] | .name_labels' config/datadog/ --value
hq 'resource.github_team[*] | .name_labels' config/github/ --value
hq 'resource[*] | .name_labels' config/snowflake/ --value
hq 'inputs' terragrunt.hcl --json
hq 'plugin[*]' .tflint.hcl --value
```

For output modes, exit codes, and all flags, see [hq Reference](04_hq.md).

**Tip:** Use `--ndjson` for directory queries (streams, works with `head`/`grep`/`jq`). Use `--json` for single files or when you need a parseable array.

**Performance:** When querying 20+ files with `--json` or `--ndjson`, `hq` automatically parallelizes across CPU cores. Use `--jobs 0` to force serial, or `--jobs N` to set an explicit worker count.
