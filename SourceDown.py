from sublime import Region
import sublime_plugin
import os.path as path
import Default.comment as comment_lib

def LOG(*args):
    print("SOURCEDOWN: ", *args)


LANG_CODES = {
    'text.html.markdown': 'markdown'
}


def language_name(scope):
    for s in scope.split(' '):
        if s.startswith("source.") or s.startswith("text."):
            return LANG_CODES.get(s, s.split('.')[1])

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


class InsertExactlyCommand(sublime_plugin.TextCommand):
    def run(self, edit, characters=""):
        self.view.insert(edit, 0, characters)


COMMENTS = {}

# REWRITE:
#     Should use selectors to locate chunks of comments
#     But then construct a string that should replace the whole contents at the
#     end. Would make it easier to not suffer from offset problems and support
#     selections.
class SourceDownCommand(sublime_plugin.TextCommand):

    def run(self, edit,
            replace=None, whole_view=None,
            extension=None,
            fenced=None, ignore_line_comments=None):
        # TODO:
        #  + add a gobble param to eat indentation?
        #  + strip empty lines?
        #  + ignore indented comments?
        view = self.view
        win = self.view.window()

        if whole_view is None:
            whole_view = view.sel()[0].size() > 0
        if replace is None:
            replace = view.settings().get("sourcedown_replace", False)
        if extension is None:
            extension = view.settings().get("sourcedown_extension", "md")
        if fenced is None:
            fenced = view.settings().get("sourcedown_fenced", True)
        if ignore_line_comments is None:
            ignore_line_comments = view.settings().get("sourcedown_ignore_line_comments", False)

        block_comments = view.find_by_selector("comment.block")
        line_comments = []
        for c in view.find_by_selector("comment.line"):
            r = Region(view.line(c).begin(), c.begin())
            if len(view.substr(r).strip(' \t')) == 0 and ' ' in view.substr(c):
                line_comments.append(c)

        comments = mergeRegions(block_comments, line_comments)
        # comments.reverse()

        LOG(block_comments)
        LOG(line_comments)
        LOG(comments)

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
            LOG(line_delim); LOG(block_delim)
            code = Region(last, c.begin())
            code_txt = view.substr(code).strip(' \t\n')
            if code.size() > 0 and code_txt:
                mdtxt += insert_code_block(code_txt, c)

            txt = view.substr(c).lstrip(' \t\n')
            if line_delim and txt.startswith(line_delim[0][0]):
                txt = '\n'.join([l.strip('\t ')[len(line_delim[0][0]):] for l in txt.splitlines()])
            elif block_delim and txt.startswith(block_delim[0][0]):
                txt = txt[len(block_delim[0][0]):-len(block_delim[0][1])]

            if txt:
                mdtxt += txt + '\n'
            last = c.end()

        if last < view.size():
            code = Region(last, view.size())
            mdtxt += insert_code_block(view.substr(code), code)

        syntax = view.settings().get("sourcedown_syntax", "Packages/Markdown/Markdown.tmLanguage")
        if not replace:
            newview = win.new_file()
            newview.set_scratch(True)
            name, _ = path.splitext(path.basename(view.file_name()))
            newview.set_name(name+'.'+extension)
            newview.run_command("insert_exactly", {"characters": mdtxt})
            newview.set_syntax_file(syntax)
            return
        else:
            view.replace(edit, Region(0, view.size())) # CHANGE FOR MULTIPLE SEL
            view.set_syntax_file(syntax)



class SourceUpCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        # TODO: everything!
        pass
