import os
from os import PathLike
from typing import Optional, cast, List, Any

import fileutils
from fs import FS, File, Directory
from logs import Logger
from server import Template
from typings import LoggerLike


class Reporter:

    def __init__(self,
                 fs: FS,
                 templates_dir: PathLike,
                 *,
                 logger: Optional['LoggerLike'] = None):
        self.fs = fs
        self.templates_dir = os.fspath(templates_dir)
        if logger is None:
            logger = Logger.get_logger('engine')
        self.logger = logger

        # The home directory for storing HTML files.
        self.root_dir = fileutils.mkdir(fileutils.get_home_dir(), '.hot-diagnose')

        # The dict of templates infomation whose key is the templates' name and the value is the templates' text.
        self.template_dict = dict()

        # The dict of file context whose key is the HTML files' name and the value is its context dict. The HTML files
        # are generated according to tamplates above while the context is generated by executed files.
        self.template_context = dict({
                'Directories': [],
                'Files': []
            })

    def prepare(self):
        fs = FS(self.templates_dir, logger=self.logger)

        def _append_dict(target):
            if isinstance(target, File):
                target = cast(File, target)
                self.template_dict[target.basename] = str(target)

        for _ in fs.walk(hook=_append_dict):
            pass

    def _walk_hook(self, target: File | Directory) -> None:
        if isinstance(target, File):
            target = cast(File, target)
            self.template_context['Files'].append(target)
        elif isinstance(target, Directory):
            target = cast(Directory, target)
            self.template_context['Directories'].append(target)
        else:
            self.logger.warning(f"Unexpected file {target}")

    def build_htmls(self):
        for _ in self.fs.walk(hook=self._walk_hook):
            pass

        self.template_context.update({'escape': escape, 'len': len, 'is_multiple': is_multiple})

        template = Template(self.template_dict['index.html'], self.template_context)
        fileutils.write_file(os.path.join(self.root_dir, 'index.html'), template.render())
        fileutils.write_file(os.path.join(self.root_dir, 'index.css'), self.template_dict['index.css'])
        fileutils.write_file(os.path.join(self.root_dir, 'control.js'), self.template_dict['control.js'])

    def report(self):
        import webbrowser
        webbrowser.open(os.path.join(self.root_dir, 'index.html'))


def escape(line: str):
    return line.replace("&", "&amp;").replace(" ", "&nbsp;").replace("<", "&lt;")


def is_multiple(contents: List[Any]):
    return len(contents) > 1
