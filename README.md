# SourceDown plugin for Sublime Text

Convert your commented scripts into Markdown documents.
Can be useful for blog/forum posts, tutorials, basic literate programming/scripting.

The comments get uncommented and the code gets fenced/indented.
Your comments are copied verbatim so if they contain valid Markdown it will be rendered correctly.
The package supports any language supported by Sublime Text (it uses scopes to detect comments).

## Installation

 1. Install [Sublime Text](http://www.sublimetext.com/)
 2. Install the plugin either:
 
     - with **Package Control** (recommended): see <https://sublime.wbond.net/docs/usage>, or
     - **manually**: by cloning this repository in your Sublime Text Package directory

## Features

The `source_down` command transforms the contents of the current view into a Markdown file containing code snippets as raw text and comments as main text.

For example

```python
# # This is an example
# 
# This `script` is *awesome*!
# Just run it with
# 
#     > python awesome.py
# 
# And enjoy!

print("awesome") # TODO: add functionality
```

is turned into

    # This is an example

    This `script` is *awesome*!
    Just run it with

        > python awesome.py

    And enjoy!

    ```python
    print("awesome") 
    ```

    TODO: add functionality

Which in turn can be compiled to

- - -

> # This is an example
> 
> This `script` is *awesome*!
> Just run it with
> 
>     > python awesome.py
> 
> And enjoy!
> 
> ```python
> print("awesome") 
> ```
> 
> TODO: add functionality

- - -


# Options

#### `fenced` (default: `true`)

Use the fenced GFM syntax for code snippets.
If the snippet contains backticks than the fence will be extended until it is not ambiguous where it ends (see [Pandoc](http://johnmacfarlane.net/pandoc/README.html#fenced-code-blocks)).

#### `ignore_code` (default: `false`)

This only processes the comments for producing the Markdown version.

#### `convert_line_comments` (default: `"lonely"`)

Line comments are the ones starting with a marker and ending with the end of the line.
This setting can take the values:

 * `"all"`: all line comments will be converted to Markdown text;
 * `"none"`: all line comments will be left as comments in the raw code block they belong to;
 * `"lonely"`: only the "standalone" line comments, i.e. the ones taking the full line, will be converted.

#### `convert_block_comments` (default: `true`)

This setting controls whether the block comments (the ones with start and end delimiters)  are converted to Markdown text or left as comments in the raw code block they belong to.

#### `keep_comments_beyond_level` (default: `2`)

Comments indented at a level greater than the one indicated will be kept as comments in a raw code block.

#### `deindent_code` (default: `false`)

If true, the raw code blocks generated from code snippets will be deindented. 

#### `deindent_comments` (default: `true`)

If true, the Markdown text extracted from comments will be deindented. 

#### `guess_comments_indent_from_first_line` (default: `true`)

If true, the indentation level will take in account where the first line of a block comment starts. For example

```c
a = 0 /* The following line
         will be deindented to level 0 */
```

gets converted to

    ```c
    a = 0
    ```
    
    The following line
    will be deindented to level 0


#### `extension` (default: `"md"`)

This is the file extension associated to Markdown files.
