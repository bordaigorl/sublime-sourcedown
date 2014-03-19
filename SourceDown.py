import sublime
from sublime import Region
import sublime_plugin
import os.path as path
import Default.comment as comment_lib

ST3 = int(sublime.version()) >= 3000


def LOG(*args):
    print("SOURCEDOWN: ", *args)


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


def mergeRegions(r1, r2):
    """
        Assumes ordered non overlapping regions.
    """
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
    return r + r1[a:] + r2[b:]


if ST3:
    def append_to_view(view, text):
        view.run_command('append', {
            'characters': text,
        })
        return view
else: # 2.x
    def append_to_view(view, text):
        new_edit = view.begin_edit()
        view.insert(new_edit, view.size(), text)
        view.end_edit(new_edit)
        return view


def gobble_spaces(gobble, txt):
    gtxt = ""
    i = 0
    while i < len(txt):
        k = i
        while i < len(txt) and i-k < gobble and txt[i] in " \t":
            i += 1
        j = i
        while i < len(txt) and txt[i] != '\n':
            i += 1
        gtxt += txt[j:i]
        if i < len(txt) and txt[i] == '\n':
            gtxt += '\n'
        i += 1
    return gtxt


class SourceDownCommand(sublime_plugin.TextCommand):

    def run(self, edit,
            target=None,
            fenced=None, ignore_line_comments=None,
            ignore_indented_comments=None,
            respect_indent_in_comment_blocks=None,
            comments_only=None,
            deindent_code=None):
        # TODO:
        #  + add target: clipboard, new, replace
        #  + handle selection (only one at first, multiple time permitting)
        #  + ignore_code_blocks: so we can just extract documentation
        view = self.view
        win = self.view.window()

        if target is None:
            target = view.settings().get("sourcedown_default_target", "new")
        if fenced is None:
            fenced = view.settings().get("sourcedown_fenced", True)
        if ignore_line_comments is None:
            ignore_line_comments = view.settings().get("sourcedown_ignore_line_comments", False)
        if comments_only is None:
            comments_only = view.settings().get("sourcedown_comments_only", False)
        if ignore_indented_comments is None:
            ignore_indented_comments = view.settings().get("sourcedown_ignore_indented_comments", True)
        if respect_indent_in_comment_blocks is None:
            respect_indent_in_comment_blocks = view.settings().get("sourcedown_respect_indent_in_comment_blocks", False)
        if deindent_code is None:
            deindent_code = view.settings().get("sourcedown_deindent_code", True)

        extension = view.settings().get("sourcedown_extension", "md")

        tab_size =  int(view.settings().get('tab_size', 8))

        # Extract block comment regions
        block_comments = []
        if ignore_indented_comments:
            for c in view.find_by_selector("comment.block"):
                r = Region(view.line(c).begin(), c.begin())
                pre = view.substr(r)
                if not (pre.startswith("\t") or pre.startswith(" "*tab_size)):
                    setattr(c, "is_block", True)
                    block_comments.append(c)
        else:
            block_comments = view.find_by_selector("comment.block")
            for c in block_comments:
                setattr(c, "is_block", True)

        # Extract standalone line comment regions
        line_comments = []
        if not ignore_line_comments:
            for c in view.find_by_selector("comment.line"):
                r = Region(view.line(c).begin(), c.begin())
                pre = view.substr(r)
                # Check if standalone comment:
                if len(pre.strip(' \t')) == 0 and ' ' in view.substr(c):
                    # Check if indented:
                    if not (ignore_indented_comments and
                       (pre.startswith("\t") or pre.startswith(" "*tab_size))):
                        setattr(c, "is_block", False)
                        line_comments.append(c)

        # Probably a good idea would be to add a field to the regions to tell
        # whether they are line or block comments
        comments = mergeRegions(block_comments, line_comments)

        # LOG(block_comments)
        # LOG(line_comments)
        # LOG(comments)

        if fenced:
            comm_end = "\n```\n\n"
            def insert_code_block(txt, region):
                start = "\n```"+language_name(view.scope_name(region.begin()))+"\n"
                return start+txt+comm_end
        else:
            comm_end = "\n"
            def insert_code_block(txt, region):
                return "\n    "+txt.replace('\n', '\n'+(' '*4))+comm_end

        mdtxt = ""
        last = 0
        for c in comments:
            (line_delim, block_delim) = comment_lib.build_comment_data(view, c.begin())
            # LOG(line_delim); LOG(block_delim)

            code = Region(last, c.begin())
            # rewrite: gobble indent if needed
            code_txt = view.substr(code).lstrip('\n').rstrip(' \t\n')
            if code.size() > 0 and code_txt:
                mdtxt += insert_code_block(code_txt, c)

            # rewrite maybe using splitlines() and processing each line
            # block:
            #  1. strip before and after
            #  2. detect min indent if needed and remove
            # line:
            #  1. strip before
            #  2. remove comment symbol
            #  3. unindent (?)
            txt = view.substr(c).lstrip(' \t\n')
            if line_delim and txt.startswith(line_delim[0][0]):
                txt = '\n'.join([l.strip('\t ')[len(line_delim[0][0]):].strip('\t ') for l in txt.splitlines()])
            elif block_delim and txt.startswith(block_delim[0][0]):
                txt = view.substr(c).rstrip(' \t\n')
                txt = txt[len(block_delim[0][0]):-len(block_delim[0][1])].strip('\t ')

            if txt:
                mdtxt += txt + '\n'
            last = c.end()

        if last < view.size():
            code = Region(last, view.size())
            codetxt = view.substr(code).strip('\n\t ')
            if codetxt:
                mdtxt += insert_code_block(codetxt, code)

        syntax = view.settings().get("md_syntax", "Packages/Markdown/Markdown.tmLanguage")
        if target == "new":
            newview = win.new_file()
            newview.set_scratch(True)
            if view.file_name():
                name, _ = path.splitext(path.basename(view.file_name()))
            else:
                name = "untitled"
            newview.set_name(name+'.'+extension)
            append_to_view(newview, mdtxt)
            newview.set_syntax_file(syntax)
        elif target == "clipboard":
            sublime.set_clipboard(mdtxt)
            sublime.set_status("SourceDown: Markdown copied to clipboard")
        elif target == "replace":
            # TODO: Handle multiple sel
            view.replace(edit, Region(0, view.size()), mdtxt)
            view.set_syntax_file(syntax)
        else:
            print()
            sublime.set_status("SourceDown: Unknown target!")



class SourceUpCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        # TODO: everything! (markup.raw.block)
        pass

