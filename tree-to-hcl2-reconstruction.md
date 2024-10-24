# Writing HCL2 from Python

Version 5 of this library supports reconstructing HCL files directly from
Python. This guide details how the reconstruction process takes place. See
also: [Limitations](#limitations)

There are three major phases:

- [Building a Python Dictionary](#building-a-python-dictionary)
- [Building an AST](#building-an-ast)
- [Reconstructing the file from the AST](#reconstructing-the-file-from-the-ast)

## Example

To create the `example.tf` file with the following content:

```terraform
resource "aws_s3_bucket" "bucket" {
  bucket = "bucket_id"
  force_destroy = true
}
```

You can use the `hcl2.Builder` class like so:

```python
import hcl2

example = hcl2.Builder()

example.block(
    "resource",
    ["aws_s3_bucket", "bucket"],
    bucket="bucket_id",
    force_destroy=True,
)

example_dict = example.build()
example_ast = hcl2.reverse_transform(example_dict)
example_file = hcl2.writes(example_ast)

print(example_file)
# resource "aws_s3_bucket" "bucket" {
#   bucket = "bucket_id"
#   force_destroy = true
# }
#
```

This demonstrates a couple of different phases of the process worth mentioning.

### Building a Python dictionary

The `hcl2.Builder` class produces a dictionary that should be identical to the
output of `hcl2.load(example_file, with_meta=True)`. The `with_meta` keyword
argument is important here. HCL "blocks" in the Python dictionary are
identified by the presence of `__start_line__` and `__end_line__` metadata
within them. The `Builder` class handles adding that metadata. If that metadata
is missing, the `hcl2.reconstructor.HCLReverseTransformer` class fails to
identify what is a block and what is just an attribute with an object value.
Without that metadata, this dictionary:

```python
{
    "resource": [
        {
            "aws_s3_bucket": {
                "bucket": {
                    "bucket": "bucket_id",
                    "force_destroy": True,
                    # "__start_line__": -1,
                    # "__end_line__": -1,
                }
            }
        }
    ]
}
```

Would produce this HCL output:

```terraform
resource = [{
    aws_s3_bucket = {
        bucket = {
            bucket = "bucket_id"
            force_destroy = true
        }
    }
}]
```

(This output parses to the same datastructure, but isn't formatted in blocks
as desired by the user. Therefore, using the `Builder` class is recommended.)

### Building an AST

The `hcl2.reconstructor.HCLReconstructor` class operates on an "abstract
syntax tree" (`hcl2.AST` or `Lark.Tree`, they're the same.) To produce this AST
from scratch in Python, use `hcl2.reverse_transform(hcl_dict)`, and to produce
this AST from an existing HCL file, use `hcl2.parse(hcl_file)`.

You can also build these ASTs manually, if you want more control over the
generated HCL output. If you do this, though, make sure the AST you generate is
valid within the `hcl2.lark` grammar.

Here's an example, which would add a "tags" element to that `example.tf` file
mentioned above.

```python
from copy import deepcopy
from lark import Token, Tree
import hcl2


def build_tags_tree(base_indent: int = 0) -> Tree:
    # build Tree representing following HCL2 structure
    # tags = {
    #   Name = "My bucket"
    #   Environment = "Dev"
    # }
    return Tree('attribute', [
        Tree('identifier', [
            Token('NAME', 'tags')
        ]),
        Token('EQ', '='),
        Tree('expr_term', [
            Tree('object', [
                Tree('new_line_or_comment', [
                    Token('NL_OR_COMMENT', '\n' + '  ' * (base_indent + 1)),
                ]),
                Tree('object_elem', [
                    Tree('identifier', [
                        Token('NAME', 'Name')
                    ]),
                    Token('EQ', '='),
                    Tree('expr_term', [
                        Token('STRING_LIT', '"My bucket"')
                    ])
                ]),
                Tree('new_line_and_or_comma', [
                    Tree('new_line_or_comment', [
                        Token('NL_OR_COMMENT', '\n' + '  ' * (base_indent + 1)),
                    ]),
                ]),
                Tree('object_elem', [
                    Tree('identifier', [
                        Token('NAME', 'Environment')
                    ]),
                    Token('EQ', '='),
                    Tree('expr_term', [
                        Token('STRING_LIT', '"Dev"')
                    ])
                ]),
                Tree('new_line_and_or_comma', [
                    Tree('new_line_or_comment', [
                        Token('NL_OR_COMMENT', '\n' + '  ' * base_indent),
                    ]),
                ]),
            ]),
        ])
    ])


def is_bucket_block(tree: Tree) -> bool:
    # check whether given Tree represents `resource "aws_s3_bucket" "bucket"`
    try:
        return tree.data == 'block' and tree.children[2].value == '"bucket"'
    except IndexError:
        return False


def insert_tags(tree: Tree, indent: int = 0) -> Tree:
    # Insert tags tree and adjust surrounding whitespaces to match indentation
    new_children = [*tree.children.copy(), build_tags_tree(indent)]
    # add indentation before tags tree
    new_children[len(tree.children) - 1] = Tree('new_line_or_comment', [
        Token('NL_OR_COMMENT', '\n  ')
    ])
    # move closing bracket to the new line
    new_children.append(
        Tree('new_line_or_comment', [
            Token('NL_OR_COMMENT', '\n')
        ])
    )
    return Tree(tree.data, new_children)


def process_token(node: Token, indent=0):
    # Print details of this token and return its copy
    print(f'[{indent}] (token)\t|', ' ' * indent, node.type, node.value)
    return deepcopy(node)


def process_tree(node: Tree, depth=0) -> Tree:
    # Recursively iterate over tree's children
    # the depth parameter represents recursion depth,
    #   it's used to deduce indentation for printing tree and for adjusting whitespace after adding tags
    new_children = []
    print(f'[{depth}] (tree)\t|', ' ' * depth, node.data)
    for child in node.children:
        if isinstance(child, Tree):
            if is_bucket_block(child):
                block_children = child.children.copy()
                # this child is the Tree representing block's actual body
                block_children[3] = insert_tags(block_children[3], depth)
                # replace original Tree with new one including the modified body
                child = Tree(child.data, block_children)

            new_children.append(process_tree(child, depth + 1))

        else:
            new_children.append(process_token(child, depth + 1))

    return Tree(node.data, new_children)


def main():
    tree = hcl2.parse(open('example.tf'))
    new_tree = process_tree(tree)
    reconstructed = hcl2.writes(new_tree)
    open('example_reconstructed.tf', 'w').write(reconstructed)


if __name__ == "__main__":
    main()

```

### Reconstructing the file from the AST

Once the AST has been generated, you can convert it back to valid HCL using
`hcl2.writes(ast)`. In the above example, that conversion is done in the
`main()` function.

## Limitations

- Some formatting choices are impossible to specify via `hcl2.Builder()` and
  require manual intervention of the AST produced after the `reverse_transform`
  step.

    - Most notably, this means it's not possible to generate files containing
      comments (both inline and block comments)

- Even when parsing a file directly and writing it back out, some formatting
  information may be lost due to Terminals discarded during the parsing process.
  The reconstructed output should still parse to the same dictionary at the end
  of the day though.
