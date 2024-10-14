Given `example.tf` file with following content

```terraform
resource "aws_s3_bucket" "bucket" {
  bucket = "bucket_id"
  force_destroy   = true
}
```

below code will add a `tags` object to the S3 bucket definition. The code can also be used to print out readable representation of **any** Parse Tree (any valid HCL2 file), which can be useful when working on your own logic for arbitrary Parse Tree manipulation.

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
