import re
import os
import sys
import multiprocessing
import importlib
import os.path
import timeit

import cProfile


class FileEntry(object):
    """
        Class representing a file in the mod directory. This
        contains all processed nodes within the file data.
    """
    path = None
    global_functions = None
    bound_functions = None
    datablocks = None

    def __init__(self, path):
        self.path = path
        self.global_functions = [ ]
        self.bound_functions = { }
        self.datablocks = [ ]

class Function(object):
    """
        Class representing a Function entity in the game code tree
        that the parse stage produces.
    """
    name = None
    parameters = None
    type = None
    filepath = None
    line = None

    aliases = None
    comments = None

    def __init__(self, name, type, parameters, filepath, line):
        self.name = name
        self.parameters = parameters
        self.filepath = filepath
        self.line = line
        self.aliases = [ ]
        self.type = type

class Global(object):
    """
        Class representing a global variable. This is currently unused
        in the coding.
    """
    name = None

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "$%s" % self.name

class Datablock(object):
    """
        Class representing a datablock entry. It contains the type, derived
        datablock name, the datablock name itself and all assigned properties.
    """
    name = None
    type = None
    derived = None
    line = None

    aliases = None
    properties = None
    filepath = None
    comments = None

    def __init__(self, name, type, properties, filepath, line, derived):
        self.name = name
        self.type = type
        self.derived = derived
        self.line = line
        self.aliases = [ ]
        self.properties = properties
        self.filepath = filepath

def scrape_file(input):
    """
        This method is a performance critical code segment in the scraper.
        It is what performs the initial parsing step to produce a sort of
        high level representation of the mod for later steps to process
        and eventually output.
    """
    filepath, parameter_split, combined_pattern = input

    key_value_pattern = re.compile("(?<!.)\s*[A-z]+\s*=.+;")

    global_usages = re.compile("\{.*\$[A-z]+(::([A-z]+))*?.*\}")
    global_pattern = re.compile("(?<!.)\s*$[A-z]+(::([A-z]+))*?")

    parameter_split = re.compile("\s*,\s*")
    assignment_split = re.compile("\s*=\s*")

    comment_pattern = re.compile("//.*")

    with open(filepath, "r") as handle:
        file = FileEntry(filepath)

        file_data = handle.read()

        # Parse for all sequences now
        for match in re.finditer(combined_pattern, file_data):
            line = file_data[0:match.start()].count("\n") + 1

            match_text = match.group(0).strip()
            if (match_text[0:8] == "function"):
                # :: Can't occur correctly in TS in just the function body, so we determine bound functions via the
                # presence of ::

                if ("::" in match_text):
                    match_split = match.group(0).strip()[9:].split("::")
                    type = match_split[0].lower()

                    match_split = match_split[1].split("(")
                    name = match_split[0].lower()
                    match_split = match_split[1].replace(")", "").split(",")

                    parameters = [ ]
                    for parameter in match_split:
                        if (parameter == ""):
                            continue

                    parameters.append(parameter.lstrip().rstrip())

                    file.bound_functions.setdefault(type, [])
                    file.bound_functions[type].append(Function(name, type, parameters, filepath, line))
                else:
                    match_split = match.group(0).strip()[9:].split("(")
                    name = match_split[0].lower()

                    match_split = re.split(parameter_split, match_split[1].replace(")", ""))

                    parameters = [ ]
                    for parameter in match_split:
                        if (parameter == ""):
                            continue

                    parameters.append(parameter.strip())
                    file.global_functions.append(Function(name, None, parameters, filepath, line))
            else:
                line = file_data[0:match.start()].count("\n") + 1
                match_text = match.group(0).lstrip().rstrip()

                header = match_text[0:match_text.find("{")]
                type = header[10:header.find("(")].strip().lower()
                name = header[header.find("(") + 1:header.find(")")].strip().lower()

                # Rip off commenting that we sometimes get in our lines
                header = re.sub(comment_pattern, "", header).rstrip()

                # Inherited?
                inherited = None
                inheritor = header.find(":")

                if (inheritor != -1):
                    inherited = [header[inheritor + 1:].strip().lower()]

                # Blow through key, values
                properties = { }
                for property_match in re.finditer(key_value_pattern, match_text):
                    property_text = property_match.group(0)

                    key, value = re.split(assignment_split, property_text, 1)
                    key = key.lstrip().lower()

                    value = value.rstrip().rstrip(";")

                    # Global reference
                    if (value[0] == "$"):
                        value = Global(value[1:])
                    # String
                    elif (value[0] == "\""):
                        value = value[1:value.rfind("\"")]
                    # Numerics
                    else:
                        try:
                            value = float(value)
                        except ValueError as e:
                            # If this was raised, treat it as a string
                            pass

                    properties[key] = value

                file.datablocks.append(Datablock(name, type, properties, filepath, line, inherited))

        return (file.global_functions, file.bound_functions, file.datablocks, file)

class TSScraper(object):
    _process_count = None
    _target_directories = None
    _dependencies = None

    _combined_pattern = re.compile("(?<!.)\s*function\s+(([A-z]|_))+(::([A-z]|_)+)*\(\s*(%[A-z]+(\s*,\s*%[A-z]+)*)*\s*\)|((?<!.)\s*datablock\s+[A-z]+\s*\(\s*\S+\s*\)\s*(:\s*[A-z]+)?\s*(//.*)?\s*\{(\s|\S)*?\s*(?<!.)\s*\};)")

    bound_function_pattern = re.compile("(?<!.)\s*function\s+(([A-z]|_)+::)([A-z]|_)+\(\s*(%[A-z]+(\s*,\s*%[A-z]+)*)*\s*\)")
    function_pattern = re.compile("(?<!.)\s*function\s+([A-z]|_)+\(\s*(%[A-z]+(\w*,\s*%[A-z]+)*)*\s*\)")

    function_pattern = re.compile("(?<!.)\s*function\s+(([A-z]|_)+::)([A-z]|_)+\(\s*(%[A-z]+(\w*,\s*%[A-z]+)*)*\s*\)")

    datablock_pattern = re.compile("(?<!.)\s*datablock\s+[A-z]+\s*\(\s*\S+\s*\)\s*(:\s*[A-z]+)?\s*(//.*)?\s*\{(\s|\S)*?\s*(?<!.)\};")

    key_value_pattern = re.compile("(?<!.)\s*[A-z]+\s*=\s*(\S+);")

    #block_iterator = re.compile("function\s+[A-z]+\s*\(\s*(%[A-z]+(\w*,\s*%[A-z]+)*)*\s*\)\{\S*\}")

    # (?<!{)\s*\$[A-z]+(::([A-z]+))*?\s*(?!})
    global_usages = re.compile("\{.*\$[A-z]+(::([A-z]+))*?.*\}")
    global_pattern = re.compile("(?<!.)\s*$[A-z]+(::([A-z]+))*?")

    parameter_split = re.compile("\s*,\s*")
    assignment_split = re.compile("\s*=\s*")


    _log_lines = None

    # Rules for verifying datablock information
    _datablock_rules = {
        "tracerprojectiledata": {
            "references": [ ],
            "optional_references": [ "projectile", "item", "sound", "splash", "explosion" ],
            "declared": [ ],
            "checks": {
                "fizzletimems": (lambda x: x >= 0, "Cannot use negative fizzle time!")
            }
        },

        "shapebaseimagedata": {
            "references": [ ],
            "optional_references": [ ],
            "declared": [ "shapefile" ],
            "checks": {
            }
        },

        "itemdata": {
            "references": [ ],
            "optional_references": [ "image" ],
            "declared": [ ],
            "checks": { "pickupradius": (lambda x: x >= 1, "Items should have >= 1 pickup radius.")
            }
        },

        "audioprofile": {
            "references": [ "description" ],
            "optional_references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "simdatablock": {
            "references": [ ],
            "optional_references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "jeteffectdata": {
            "references": [ ],
            "optional_references": [ ],
            "declared": [ "texture" ],
            "checks": { },
        },

        "hovervehicledata": {
            "references": [ ],
            "optional_references": [ ],
            "declared": [ "catagory" ],
            "checks": { "dragforce": (lambda x: x >= 0.01, "dragForce must be at least 0.01"),
                        "vertfactor": (lambda x: x >= 0 and x <= 1.0, "vertFactor must be >= 0 && <= 1.0"),
                        "floatingthrustfactor": (lambda x: x >= 0 and x <= 1.0, "floatThrustFactor must be >= 0 && <= 1.0") },
        },

        "stationfxpersonaldata": {
            "optional_references": [ ],
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "cameradata": {
            "optional_references": [ ],
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "triggerdata": {
            "optional_references": [ ],
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "wheeledvehicledata": {
            "optional_references": [ ],
            "references": [ ],
            "declared": [ "catagory" ],
            "checks": { },
        },

        "tsshapeconstructor": {
            "optional_references": [ ],
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "bombprojectiledata": {
            "optional_references": [ ],
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "stationfxvehicledata": {
            "optional_references": [ ],
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "runninglightdata": {
            "optional_references": [ ],
            "references": [ ],
            "declared": [ ],
            "checks": { "radius": (lambda x: x >= 1, "Lights should have a radius of >= 1.") },
        },

        "staticshapedata": {
            "optional_references": [ ],
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "decaldata": {
            "references": [ ],
            "optional_references": [ ],
            "declared": [ "texturename" ],
            "checks": { },
        },

        "repairprojectiledata": {
            "references": [ ],
            "optional_references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "explosiondata": {
            "references": [ ],
            "optional_references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "linearprojectiledata": {
            "optional_references": [ ],
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "elfprojectiledata": {
            "optional_references": [ ],
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "linearflareprojectiledata": {
            "optional_references": [ ],
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "sensordata": {
            "references": [ ],
            "optional_references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "forcefieldbaredata": {
            "optional_references": [ ],
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "particledata": {
            "references": [ ],
            "optional_references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "particleemitterdata": {
            "references": [ "particles" ],
            "optional_references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "playerdata": {
            "references": [ ],
            "optional_references": [ ],
            "declared": [ ],
            "checks": { "shapefile": (lambda x: x is not None and x != "", "Must have a valid shapefile!") },
        },

        "turretdata": {
            "references": [ ],
            "optional_references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "turretimagedata": {
            "references": [ ],
            "optional_references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "shockwavedata": {
            "references": [ ],
            "optional_references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "seekerprojectiledata": {
            "references": [ ],
            "optional_references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "debrisdata": {
            "references": [ ],
            "declared": [ ],
            "optional_references": [ ],
            "checks": { },
        },

        "grenadeprojectiledata": {
            "references": [ ],
            "optional_references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "sniperprojectiledata": {
            "references": [ ],
            "declared": [ ],
            "optional_references": [ ],
            "checks": { },
        },

        "sniperprojectiledata": {
            "references": [ ],
            "optional_references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "flyingvehicledata": {
            "references": [ ],
            "optional_references": [ ],
            "declared": [ "catagory" ],
            "checks": { },
        },

        "splashdata": {
            "references": [ ],
            "declared": [ ],
            "optional_references": [ ],
            "checks": { },
        },

        "energyprojectiledata": {
            "references": [ ],
            "declared": [ ],
            "optional_references": [ ],
            "checks": { },
        },

        "flareprojectiledata": {
            "references": [ ],
            "optional_references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "targetprojectiledata": {
            "references": [ ],
            "declared": [ ],
            "optional_references": [ ],
            "checks": { },
        },

        "shocklanceprojectiledata": {
            "references": [ ],
            "declared": [ ],
            "optional_references": [ ],
            "checks": { },
        },

        "effectprofile": {
            "references": [ ],
            "declared": [ ],
            "optional_references": [ ],
            "checks": { },
        },

        "precipitationdata": {
            "references": [ ],
            "optional_references": [ ],
            "declared": [ ],
            "checks": { },
        },

        "commandericondata": {
            "references": [ ],
            "optional_references": [ ],
            "declared": [ ],
            "checks": { },
       },

        "missionmarkerdata": {
            "references": [ ],
            "optional_references": [ ],
            "declared": [ ],
            "checks": { },
       },

       "particleemissiondummydata": {
            "references": [ ],
            "declared": [ ],
            "optional_references": [ ],
            "checks": { },
      },

      "fireballatmospheredata": {
            "references": [ ],
            "optional_references": [ ],
            "declared": [ ],
            "checks": { },
      },

      "audiodescription": {
          "references": [ ],
          "optional_references": [ ],
          "declared": [ ],
          "checks": { },
      },

      "lightningdata": {
          "references": [ ],
          "declared": [ ],
          "checks": { },
          "optional_references": [ ],
      },

      "audioenvironment": {
          "references": [ ],
          "optional_references": [ ],
          "declared": [ ],
          "checks": { },
      },
    }

    def __init__(self, target_directory, process_count = 0, previous_results = None):
        self._process_count = process_count
        self._target_directory = target_directory
        self.previous_results = previous_results
        self._log_lines = [ ]

    def get_file_list(self, directory):
        output = [ ]

        previous_working_directory = os.getcwd()
        os.chdir(directory)

        for root, dirs, files in os.walk("."):
            for filename in files:
                relative_path = os.path.join(root, filename)

                if (not os.path.isfile(relative_path)):
                    continue

                absolute_path = os.path.realpath(relative_path)

                # Only check TS files
                name, extension = os.path.splitext(filename)
                if (extension != ".cs"):
                    continue

                output.append((absolute_path, relative_path.lower()))

        os.chdir(previous_working_directory)
        return output

    def _parse_stage(self, target_files):
        results = None
        if (self._process_count > 0):
            # Create a list with all the required data for the multi-process
            input = [ ]

            for target_file in target_files:
                input.append((target_file, self.parameter_split, self._combined_pattern))

            pool = multiprocessing.Pool(processes=self._process_count)
            results = pool.map(scrape_file, input)
        else:
            results = [ ]

            for target_file in target_files:
                results.append(scrape_file((target_file, self.parameter_split, self._combined_pattern)))

        return results

    def _declaration_stage(self, parse_results):
         # Entries we've already processed
        processed_entries = { }

        # For each file entry
        known_datablocks = { }

        for file in parse_results:
            # For each global function
            for global_function in file.global_functions:
                processed_entries.setdefault(global_function.name, global_function)

                # Check for declarations
                if (processed_entries[global_function.name] is not global_function):
                    known_entry = processed_entries[global_function.name]

                    # Redeclaration with different param count
                    if (len(known_entry.parameters) != len(global_function.parameters)):
                        global_function.aliases.append(known_entry)
                        known_entry.aliases.append(global_function)
                        print("Warning: Global function '%s' redeclared with %u parameters in %s, line %u! (Original declaration in %s, line %u with %u parameters)" % (known_entry.name, len(global_function.parameters), global_function.filepath, global_function.line, known_entry.filepath, known_entry.line, len(known_entry.parameters)))
                    # Regular Redeclaration
                    else:
                        global_function.aliases.append(known_entry)
                        known_entry.aliases.append(global_function)
                        print("Warning: Global function '%s' redeclared in %s, line %u! (Original declaration in %s, line %u)" % (known_entry.name, global_function.filepath, global_function.line, known_entry.filepath, known_entry.line))

            processed_entries = { }

            # For each bound function
            for bound_type in file.bound_functions.keys():
                for bound_function in file.bound_functions[bound_type]:
                    processed_entries.setdefault(bound_function.type, {})
                    processed_entries[bound_function.type].setdefault(bound_function.name, bound_function)

                    # Check for declarations
                    if (processed_entries[bound_function.type][bound_function.name] is not bound_function):
                        known_entry = processed_entries[bound_function.type][bound_function.name]

                        # Redeclaration with different param count
                        if (len(known_entry.parameters) != len(bound_function.parameters)):
                            bound_function.aliases.append(known_entry)
                            known_entry.aliases.append(bound_function)
                            print("Warning: Bound function '%s::%s' redeclared with %u parameters in %s, line %u! (Original declaration in %s, line %u with %u parameters)" % (known_entry.type, known_entry.name, len(bound_function.parameters), bound_function.filepath, bound_function.line, known_entry.filepath, known_entry.line, len(known_entry.parameters)))
                        # Regular Redeclaration
                        else:
                            bound_function.aliases.append(known_entry)
                            known_entry.aliases.append(bound_function)
                            print("Warning: Bound function '%s::%s' redeclared in %s, line %u! (Original declaration in %s, line %u)" % (known_entry.type, known_entry.name, bound_function.filepath, bound_function.line, known_entry.filepath, known_entry.line))

            processed_entries = { }

            # For each datablock
            for datablock in file.datablocks:
                processed_entries.setdefault(datablock.name, datablock)

                known_datablocks.setdefault(datablock.name, [])
                known_datablocks[datablock.name].append(datablock)


        # Check for datablock declarations
        for datablock in known_datablocks:
            occurrence_count = len(known_datablocks[datablock])
            if (occurrence_count != 1):
                print("Warning: Datablock '%s' redeclared %u times!" % (datablock, occurrence_count))

                for occurrence in known_datablocks[datablock]:
                    print("   In %s:%u" % (occurrence.filepath, occurrence.line))

        return known_datablocks

    def _inheritance_stage(self, parse_results, datablock_list):
        # For each file entry
        for file in parse_results:
            # For each datablock
            for datablock in file.datablocks:
                # Process all parents
                if (datablock.derived is not None):
                    for parent in datablock.derived:
                        if (parent.lower() not in datablock_list.keys()):
                            print("Warning: Datablock '%s' derives from non-existent parent '%s'! (Declaration in %s, line %u)" % (datablock.name, parent, datablock.filepath, datablock.line))
                            datablock.derived.remove(parent)
                elif (datablock.derived is not None):
                    datablock.derived = datablock_list[datablock.derived]

    def _reference_stage(self, parse_results, datablock_list):
        # For each file entry
        for file in parse_results:
            # For each datablock
            for datablock in file.datablocks:
                if (datablock.type in self._datablock_rules):
                    # We have a bunch of rules to check, so we recurse parent classes where necessary.
                    parent_classes = [ datablock.name ]

                    # Recurse down the hierarchy
                    def process_parents(current, result):
                        if (current.derived is not None):
                            result += current.derived
                            for parent in current.derived:
                                parent_declarations = datablock_list[parent]

                                # Check for the property on each parent block
                                for parent in parent_declarations:
                                    process_parents(parent, result)
                        return result

                    process_parents(datablock, parent_classes)

                    # Flip through each reference in the table
                    references = self._datablock_rules[datablock.type]["references"] + self._datablock_rules[datablock.type]["optional_references"]
                    for reference in references:
                        found_reference = False

                        for parent in parent_classes:
                            # FIXME: Deal with datablock redeclarations?
                            parent_datablock = datablock_list[parent][0]

                            if (reference in parent_datablock.properties):
                                if (parent_datablock.properties[reference].lower() not in datablock_list.keys()):
                                    print("Reference Warning: %s Datablock '%s' references '%s' in property '%s', which does not exist! (Declaration in %s, line %u)" % (datablock.type, datablock.name, datablock.properties[reference], reference, datablock.filepath, datablock.line))
                                    break
                                else:
                                    found_reference = True
                                    break

                        if (found_reference is False and reference in self._datablock_rules[datablock.type]["references"]):
                            print("Reference Warning: %s datablock '%s' has no '%s' declaration! (Declaration in %s, line %u)" % (datablock.type, datablock.name, reference, datablock.filepath, datablock.line))

                    # Check each declaration
                    for declaration in self._datablock_rules[datablock.type]["declared"]:
                        found_declaration = False

                        for parent in parent_classes:
                            # FIXME: Deal with datablock redeclarations?
                            parent_datablock = datablock_list[parent][0]

                            if (declaration in parent_datablock.properties):
                                found_declaration = True
                                break

                        if (found_declaration is False):
                            print("Declaration Warning: %s Datablock '%s' required property '%s' not declared or inherited! (Declaration in %s, line %u)" % (datablock.type, datablock.name, declaration, datablock.filepath, datablock.line))

                    # Run custom checks
                    for check in self._datablock_rules[datablock.type]["checks"].keys():
                        found_check = False

                        for parent in parent_classes:
                            # FIXME: Deal with datablock redeclarations?
                            parent_datablock = datablock_list[parent][0]

                            # Is it declared?
                            if (check not in parent_datablock.properties.keys()):
                                continue

                            found_check = True
                            method, message = self._datablock_rules[parent_datablock.type]["checks"][check]

                            if (not method(parent_datablock.properties[check])):
                                print("Property Warning (Datablock '%s', type %s. Declaration in %s, line %u): %s" % (datablock.name, datablock.type, datablock.filepath, datablock.line, message))

                            break

                        if (found_check is False):
                            print("Inherited Property Warning: %s Datablock %s '%s' property not declared and parent datablocks do not declare it! (Declaration in %s, line %u)" % (datablock.type, datablock.name, check, datablock.filepath, datablock.line))
                else:
                    print("Program Error: Unknown datablock type '%s'! This means the software does not know how to check this datablock. (Declaration in %s, line %u)" % (datablock.type, datablock.filepath, datablock.line))

    def process(self):
        # Process each directory sequentially
        target_files = { }

        if (os.path.isdir(self._target_directory) is False):
            raise IOError("No such directory to recurse (#%u): '%s'" % (index, self._target_directory))

        print("INFO: Building file list for directory '%s' ..." % self._target_directory)
        current_files = self.get_file_list(self._target_directory)

        # Does a previous entry exist in the target file list?
        for current_absolute_path, current_relative_path in current_files:
            target_files[current_relative_path] = current_absolute_path

        # Build the list now
        target_file_list = [ ]

        for current_relative_file in target_files.keys():
            target_file_list.append(target_files[current_relative_file])

        # Perform the initial parse
        print("INFO: Performing parse stage ...")

        file_list = [ ]
        global_function_list = [ ]
        bound_function_list = { }
        datablock_list = { }
        for payload in self._parse_stage(target_file_list):
            global_functions, bound_functions, datablocks, file = payload

            file_list.append(file)
            global_function_list += global_functions

            # Write out datablocks
            for datablock in datablocks:
                datablock_list[datablock.name] = datablock

            for classname in bound_functions:
                bound_function_list.setdefault(classname, [])
                bound_function_list[classname] += bound_functions[classname]

        # Perform the declaration analysis
        print("INFO: Performing declaration analysis. ...")
        datablock_list = self._declaration_stage(file_list)

        # Combine previous datablock listings with current ones
        # TODO: Refactor the programming to use a global lookup when performing referential checks
        if (self.previous_results is not None):
            for datablock_name in self.previous_results["datablocks"]:
                # Don't overwrite current datablock listings with base ones
                if (datablock_name not in datablock_list):
                    datablock_list[datablock_name] = self.previous_results["datablocks"][datablock_name]

        # Perform DB inheritance analysis
        print("INFO: Performing datablock inheritance analysis ...")
        self._inheritance_stage(file_list, datablock_list)

        # Perform DB reference analysis
        print("INFO: Performing datablock reference analysis ...")
        self._reference_stage(file_list, datablock_list)

        # We're done, return the results
        print("INFO: Done.")

        return { "files": file_list, "datablocks": datablock_list, "bound_functions": bound_function_list,
        "global_functions": global_function_list }
