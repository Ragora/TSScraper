import re
import os
import sys
import importlib
import os.path

class Exporter(object):
    data = None
    
    def __init__(self, data):
        self.data = data
        
    def write(self):
        import jinja2
        
        # Read the template files first
        file_template = None
        with open("data/filetempl.html", "r") as handle:
            file_template = handle.read()
            
        index_template = None
        with open("data/indextempl.html", "r") as handle:
            index_template = handle.read()
        
        html_filenames = [ ]
        # For each file entry...
        for file in self.data:
            if (len(file.global_functions) == 0 and len(file.bound_functions.keys()) == 0 and len(file.datablocks) == 0):
                continue
            
            html_filename = file.path.lstrip("./").replace("/", "-")
            html_filename, oldextension = os.path.splitext(html_filename)
            html_filename = "%s.html" % html_filename
            html_filenames.append(html_filename)
            
            with open(html_filename, "w") as handle:
                template = jinja2.Template(file_template)
                handle.write(template.render(file=file.path, globals=file.global_functions))
                
        # Dump the index file
        with open("index.html", "w") as handle:
            template = jinja2.Template(index_template)
            handle.write(template.render(files=self.data))
           
        print("Done processing.")
 
