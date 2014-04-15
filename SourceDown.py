import sublime
from sublime import Region
import sublime_plugin
import os.path as path

import re

ST3 = int(sublime.version()) >= 3000

#
# # The SourceDown plugin
#
# Using this plugin you can convert your commented scripts into Markdown documents.
# This plugin is self documenting using itself.
#
# For the source code and issues see the [github repo](https://github.com/bordaigorl/sublime-sourcedown)

# ## Helper functions
#
# Here we start with some simple utility functions:
def LOG(*args):
    print("SOURCEDOWN: ", *args)


# We may need to append content to a view but if we are in ST2 we cannot use the `append` command
if ST3:
    def append_to_view(view, text):
        view.run_command('append', {
            'characters': text,
        })
        return view
else:  # 2.x
    def append_to_view(view, text):
        new_edit = view.begin_edit()
        view.insert(new_edit, view.size(), text)
        view.end_edit(new_edit)
        return view


# This is needed to match selectors and names of languages supported by GFM:
LANG_CODES = {
    'text.html.markdown': '',
    'text.html.markdown.gfm': 'md',
    'text.plain': ''
}


def language_name(scope):
    for s in scope.split(' '):
        if s.startswith("source.") or s.startswith("text."):
            return LANG_CODES.get(s, s.split('.')[1])
    return ""

# This helper function finds out which is the most likely syntax definition file associated to a language name
def find_syntax(lang, default=None):
    res = sublime.find_resources("%s.*Language" % lang)
    if res:
        return res[-1]
    else:
        return (default or ("Packages/%s/%s.tmLanguage" % (lang, lang)))

# We also may need to remove white space in a block of text
INDENT = re.compile(r'^\s*', re.M)

def deindent(txt):
    strip = None  # strip = min([len(m) for m in INDENT.findall(txt)])
    for m in INDENT.findall(txt):
        l = len(m)
        if l <= (strip or l):
            strip = l
        if strip == 0:  # stops more quickly than min
            break
    if strip > 0:
        return '\n'.join([line[strip:] for line in txt.splitlines()])
    else:
        return txt
#> TODO: replace with textwrap.dedent?


# Extract comment delimiters from syntax definitions.
# Adapted from `Default/comments.py`
def comment_delims(view, region):
    pt = region.begin()
    shell_vars = view.meta_info("shellVariables", pt)
    if not shell_vars:
        return ([], [])

    # First, transform the list of dicts into a single dict:
    all_vars = {}
    for v in shell_vars:
        if 'name' in v and 'value' in v:
            all_vars[v['name']] = v['value']

    line_comments = []
    block_comments = []

    # Second, transform the dict into a single array of valid comments
    suffixes = [""] + ["_" + str(i) for i in range(1, 10)]
    for suffix in suffixes:
        start = all_vars.setdefault("TM_COMMENT_START" + suffix)
        end = all_vars.setdefault("TM_COMMENT_END" + suffix)
        # mode = all_vars.setdefault("TM_COMMENT_MODE" + suffix)
        # disable_indent = all_vars.setdefault("TM_COMMENT_DISABLE_INDENT" + suffix)

        if start:
            sstart = start.strip()
        if start and end:
            if start != sstart:
                block_comments.append({"begin": start, "end": end})
                block_comments.append({"begin": sstart, "end": end.strip()})
            else:
                block_comments.append({"begin": start+" ", "end": end})
                block_comments.append({"begin": start, "end": end})
        elif start:
            if start != sstart:
                line_comments.append(start)
                line_comments.append(sstart)
            else:
                line_comments.append(start+" ")
                line_comments.append(start)

    return (line_comments, block_comments)


# ## Comment Region classes
#
# A proxy of Region, decorating it with extra methods:
class CommentRegion(sublime.Region):

    delim_start = ""
    delim_end = ""

    def __init__(self, view, region):
        self._region = region
        self._view = view
        self._comment_start = 0
        self._comment_end = region.size()

    def __getattr__(self, name):
        region = object.__getattribute__(self, '_region')
        return getattr(region, name)

    def line(self):
        return self._view.line(self._region)

    def prefix(self):
        return Region(self.line().begin(), self.begin())

    def postfix(self):
        return Region(self.end(), self.line().end())

    def comment_begin(self):
        return self._region.begin() + self._comment_start

    def comment_end(self):
        return self._region.begin() + self._comment_end

    def contents_begin(self):
        return self.comment_begin()+len(self.delim_start)

    def contents_end(self):
        return self.comment_end()-len(self.delim_end)

    def contents(self):
        return self._view.substr(Region(self.contents_begin(), self.contents_end()))


#> FIXME: if multiline and first has a prefix should be split in two!
class LineComment(CommentRegion):

    #> FIXME: `### A` would infer `prefix=##` and `contents=A`
    #  so maybe use min([(text.find(d), d) for d in delim if text.find(d) > 0], key=fst, default=None)
    def __init__(self, view, region):
        super(LineComment, self).__init__(view, region)
        self.delim, _ = comment_delims(view, region)
        text = view.substr(region)
        for d in self.delim:
            pos = text.find(d)
            if pos >= 0:
                self._comment_start = pos
                self.delim_start = d
                break
        self.delim_end = ""

    def strip_delim(self, text):
        for d in self.delim:
            pos = text.find(d)
            if pos >= 0:
                # print("stripped '%s' '%s'" % (d,text[pos+len(d):]))
                return text[pos+len(d):]
        return text

    def contents(self):
        split = self._view.split_by_newlines(self._region)
        if len(split) == 1:
            return self._view.substr(Region(self.contents_begin(), self.contents_end()))
        else:
            return '\n'.join([self.strip_delim(self._view.substr(r)) for r in split])

    def is_block(self):
        return False


class BlockComment(CommentRegion):

    def __init__(self, view, region):
        super(BlockComment, self).__init__(view, region)
        _, self.delim = comment_delims(view, region)
        text = view.substr(region)
        for d in self.delim:
            pos = text.find(d["begin"])
            if pos >= 0:
                self._comment_start = pos
                self.delim_start = d["begin"]
                break
        for d in self.delim:
            pos = text.rfind(d["end"])
            if pos >= 0:
                self._comment_end = pos + len(d["end"])
                self.delim_end = d["end"]
                break

    def is_block(self):
        return True

# An helper function checking whether a region is a comment region of some sort:
def is_comment(region):
    return (
        isinstance(region, CommentRegion) or
        isinstance(region, LineComment) or
        isinstance(region, BlockComment))


# ## The main command
#
# A class for the `source_down` text command
class SourceDownCommand(sublime_plugin.TextCommand):

    # The default values for the formatting options
    DEFAULTS = [
        ("fenced", True),
        ("ignore_code", False),
        ("convert_line_comments", "lonely"),
        ("convert_block_comments", True),
        ("keep_comments_beyond_level", 2),
        ("deindent_code", False),
        ("deindent_comments", True),
        ("guess_comments_indent_from_first_line", True),
        ("extension", "md")
    ]

    # Load the options from:
    #
    # 1. defaults
    # 2. then the settings in `SourceDown.sublime-settings` (Default, then User)
    # 3. and finally from the `sourcedown` key in the project's settings.
    #
    def update_options(self, options):
        settings = sublime.load_settings("SourceDown.sublime-settings")
        projsett = self.view.window().project_data().get("settings", {}).get("sourcedown", {})
        for k in projsett:
            if k not in options:
                options[k] = projsett[k]
        for (k, d) in self.DEFAULTS:
            if k not in options:
                options[k] = settings.get(k, d)
        self.options = options

    # Wrap the content of a region so that it represents raw code in markdown
    def wrap_code(self, r):
        txt = self.view.substr(r).strip('\n')
        if txt.strip() == "":
            return ""
        if self.options["deindent_code"]:
            txt = deindent(txt)
        if self.options["fenced"]:
            lang = language_name(self.view.scope_name(r.begin()))
            ticks = 3
            while txt.find('\n'+('`'*ticks)+'\n') > 0:
                ticks += 1
            fence = '`'*ticks
            return "\n%s%s\n%s\n%s\n" % (fence, lang, txt, fence)
        else:
            txt = txt.replace('\n', '\n'+(' '*4))
            return "\n    %s\n" % txt

    # Are we supposed to ignore this region?
    def is_to_ignore(self, r):
        if self.view.indentation_level(r.begin()) >= self.options["keep_comments_beyond_level"]:
            return True
        if r.is_block():
            return not self.options["convert_block_comments"]
        else:
            clc = self.options["convert_line_comments"]
            if clc == True or clc == "all":
                return False
            if clc == "lonely":
                return len(self.view.substr(r.prefix()).strip()) != 0
            return False

    # `partition_text` takes two ordered, non-overlapping lists of regions as input.
    # They represent block and line comments.
    # It computes a partition of the whole view in regions:
    # the original regions will be in the partition (provided they are not ignored)
    # and the regions of code inbetween are inserted to cover the gaps.
    def partition_text(self, r1, r2):
        """
        Assumes ordered non-overlapping regions.
        Generates ordered partition of 0..view.size
        """
        size = self.view.size()
        r = []
        a = 0
        b = 0
        while len(r1) > a and len(r2) > b:
            if r1[a].end() <= r2[b].begin():
                r.append(r1[a])
                a += 1
            else:
                r.append(r2[b])
                b += 1
        merged = r + r1[a:] + r2[b:]
        if self.options["ignore_code"]:
            return merged
        if len(merged) == 0:
            return [Region(0, size)]
        r = []
        a = 0
        prev_end = 0
        while a < len(merged):
            if not self.is_to_ignore(merged[a]):
                if merged[a].begin() - prev_end > 0:
                    r.append(Region(prev_end, merged[a].begin()))
                r.append(merged[a])
                prev_end = merged[a].end()
            a += 1
        if prev_end < size:
            r.append(Region(prev_end, size))
        return r

    # The entry point of the command:
    def run(self, edit, target="new", **options):
        view = self.view
        sublime.status_message("Generating Markdown version.")
        self.update_options(options)
        # tab_size = int(view.settings().get('tab_size', 8))

        blocks = view.find_by_selector("comment.block")
        lines = view.find_by_selector("comment.line")
        # rest is code
        blocks = [BlockComment(view, b) for b in blocks]
        lines = [LineComment(view, l) for l in lines]

        regions = self.partition_text(lines, blocks)
        sublime.status_message("Generating Markdown version..")

        result = ""
        for r in regions:
            if is_comment(r):
                contents = r.contents()
                txt = contents.strip("\n")
                if txt.strip() == "":
                    continue
                if self.options["deindent_comments"]:
                    if self.options["guess_comments_indent_from_first_line"] and \
                       r.is_block() and \
                       not contents.startswith('\n'):
                        guess = r.prefix().size() + len(r.delim_start)
                        txt = (' '*guess) + txt
                    txt = deindent(txt)
                result += "\n%s\n" % txt
            else:
                result += self.wrap_code(r)
        sublime.status_message("Generating Markdown version...")

        # - - -
        # OUTPUT
        syntax = view.settings().get("md_syntax", find_syntax("Markdown"))
        if target == "new":
            newview = self.view.window().new_file()
            newview.set_scratch(True)
            if view.file_name():
                name, _ = path.splitext(path.basename(view.file_name()))
            else:
                name = "untitled"
            newview.set_name(name+'.'+self.options["extension"])
            append_to_view(newview, result)
            newview.set_syntax_file(syntax)
            sublime.status_message("Markdown version successfully generated!")
        elif target == "clipboard":
            sublime.set_clipboard(result)
            sublime.status_message("Markdown version copied to clipboard")
        elif target == "replace":
            # TODO: Handle multiple sel
            view.replace(edit, Region(0, view.size()), result)
            view.set_syntax_file(syntax)
            sublime.status_message("Markdown version successfully replaced!")
        else:
            sublime.status_message("SourceDown: Unknown target!")


# ## Misc
#
# This has not been implemented just yet
class SourceUpCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        # TODO: everything! (markup.raw.block)
        pass


# This is meant to be used internally to generate the default `.sublime-settings` file
# from the `DEFAULTS` list
class SourceDownSettingsCommand(sublime_plugin.WindowCommand):

    def run(self):
        import json
        s = []
        i = 1
        for k, v in SourceDownCommand.DEFAULTS:
            s.append('"%s": ${%s:%s}' % (k, i, json.dumps(v)))
            i += 1
        s = "{\n    %s$0\n}" % ",\n    ".join(s)
        # print(json.dumps(json.dumps(opt, indent=4, separators=(',', ': '))))
        print(json.dumps(s))
