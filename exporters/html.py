import re
import os
import sys
import importlib
import os.path
import shutil

class Exporter(object):
    data = None

    def __init__(self, data, target_directory):
        self.data = data
        self.target_directory = target_directory

    def _path_visitor(self, arg, dirname, names):
        for name in names:
            mirrored_path = os.path.join(dirname, name)
            relative_path = os.path.join(arg, mirrored_path.replace(self.target_directory + "/", ""))

            try:
                if (os.path.isdir(mirrored_path)):
                    os.mkdir(relative_path)
            except OSError:
                pass

    def write(self, directory):
        import jinja2

        # Read the template files first
        file_template = None
        with open("data/filetempl.html", "r") as handle:
            file_template = handle.read()

        index_template = None
        with open("data/indextempl.html", "r") as handle:
            index_template = handle.read()

        html_filenames = [ ]

        # Recurse the target directory and recreate its structure
        os.path.walk(self.target_directory, self._path_visitor, directory)

        # For each file entry...
        script_relative_paths = [ ]
        for file in self.data["files"]:
            if (len(file.global_functions) == 0 and len(file.bound_functions.keys()) == 0 and len(file.datablocks) == 0):
                continue

            # First, we collapse to a file path relative to our output dir
            # FIXME: Dirty hack to make sure the os.path.join works
            html_filename = file.path.replace(self.target_directory + "/", "")
            script_relative = html_filename
            file.mod_path = html_filename
            script_relative_paths.append(script_relative)

            # Next, we ensure that the subdirectories exist
            #html_filename = html_filename.lstrip("./").replace("/", "-")
            html_filename, oldextension = os.path.splitext(html_filename)
            html_filename = "%s.html" % html_filename
            html_filenames.append(html_filename)
            file.web_path = html_filename

            with open(os.path.join(directory, html_filename), "w") as handle:
                template = jinja2.Template(file_template)
                handle.write(template.render(file=file))

        # Dump the index file
        with open(os.path.join(directory, "index.html"), "w") as handle:
            template = jinja2.Template(index_template)

            handle.write(template.render(files=self.data["files"]))

        # Puke bootstrap into the directory
        try:
            shutil.copytree("data/bootstrap", os.path.join(directory, "bootstrap"))
        except OSError:
            pass

        print("Done processing.")
