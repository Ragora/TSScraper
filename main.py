"""
    main.py
"""

import re
import os
import sys
import multiprocessing
import importlib
import os.path
import timeit

import cProfile

import tsscraper

class Application(object):
    thread_count = 8

    threads = None

    target_directory = None
    target_exporter = None

    def print_usage(self):
        print("Usage: '%s <exporter> <output directory> <target directories...>'" % sys.argv[0])
        print("Or: '%s exporters' for a list of known exporters." % sys.argv[0])

    def get_available_exporters(self):
        exporters = { }

        for root, dirs, files in os.walk("exporters"):
            for filename in files:
                module_name, extension = os.path.splitext(filename)

                if (module_name == "__init__"):
                    continue

                try:
                    module = importlib.import_module('exporters.%s' % (module_name))
                    exporters[module_name] = module
                except ImportError as e:
                    print(e)

        return exporters

    def main(self):
        """
            The main entry point of the application. This is equivalent to
            the main() method in C and C++.
        """
        if (len(sys.argv) < 2):
           self.print_usage()
           return

        exporters = self.get_available_exporters()

        if (sys.argv[1] == "exporters"):
            print("Available Exporters: ")

            for exporter in exporters:
                print("\t- %s" % exporter)
            print("\t- None")
            return
        elif(len(sys.argv) < 4):
            self.print_usage()
            return

        self.target_directory = sys.argv[3]
        self.output_directory = sys.argv[2]
        self.target_exporter = sys.argv[1]
        self.run()

    def run(self):
        exporter = None
        if (self.target_exporter.lower() != "none"):
            exporters = self.get_available_exporters()
            try:
                exporter = exporters[self.target_exporter]
            except KeyError as e:
                print("Error: No such exporter '%s'." % self.target_exporter)
                self.print_usage()
                return

        scraper = tsscraper.TSScraper(self.target_directory, self.thread_count)
        results = scraper.process()

        # Init the exporter
        if (exporter is not None):
            # Ensure that the output directory at least exists
            os.mkdir(self.output_directory)

            output = exporter.Exporter(results, self.target_directory)
            output.write(self.output_directory)

if __name__ == "__main__":
    print("Operation Completion-----------------------\n%f Seconds" % timeit.timeit("Application().main()", number=1, setup="from __main__ import Application"))
