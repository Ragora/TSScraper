import re
import os
import sys
import importlib
import os.path

class Exporter(object):
    data = None

    def __init__(self, data):
        self.data = data

    def write(self, directory):        
        with open("Out.txt", "w") as handle:
            # Write the header
            handle.write("====== Test ======\n\n")

            # For each file entry...
            for file in self.data["files"]:
                if (len(file.global_functions) == 0 and len(file.bound_functions.keys()) == 0 and len(file.datablocks) == 0):
                    continue

                # Calculate the total entry count
                entry_count = len(file.global_functions) + len(file.datablocks)
                for type in file.bound_functions.keys():
                    entry_count = entry_count + len(file.bound_functions[type])

                handle.write("===== Entries in %s (%u total) =====\n\n" % (file.path, entry_count))
                handle.write("===== Global Functions (%u total) =====\n\n" % len(file.global_functions))

                # For each global function...
                for function in file.global_functions:
                    handle.write("==== %s ====\n" % function.name)
                    handle.write("File (line %u): %s\n\n" % (function.line, file.path))

                    if (len(function.parameters) != 0):
                        handle.write("Parameters (in order):\n")

                        for parameter in function.parameters:
                            handle.write("   * %s\n" % parameter)
                    else:
                        handle.write("Parameters: None\n")

                    handle.write("\n")

                # For each known type...
                for type in file.bound_functions.keys():
                    handle.write("===== Bound Functions on %s (%u total) =====\n\n" % (type, len(file.bound_functions[type])))
                    # For each function for this type...
                    for function in file.bound_functions[type]:
                        handle.write("==== %s::%s ====\n" % (function.type, function.name))
                        handle.write("File (line %u): %s\n\n" % (function.line, file.path))

                        if (len(function.parameters) != 0):
                            handle.write("Parameters (in order):\n")

                            for parameter in function.parameters:
                                handle.write("   * %s\n" % parameter)
                        else:
                            handle.write("Parameters: None\n")

                        handle.write("\n")

        print("Done processing.")
