"""Build the examples from the Cantera repository into Nikola listings.

This plugin finds the Cantera examples directory in the Cantera repository
to process the examples into nicely formatted HTML along the lines of
Nikola listings. The Cantera examples are found in the ``EXAMPLES_FOLDERS``
configuration option from the top-level config.py.
"""
from pathlib import Path

from nikola.plugin_categories import Task
from nikola import utils
from pygments import highlight
from pygments.lexers import MatlabLexer
import natsort


def render_example_index(site, kw, headers, output_file):
    n = 3
    for head_dict in headers.values():
        head_files = head_dict["files"]
        head_dict["files"] = [
            head_files[i : i + n] for i in range(0, len(head_files), n)  # NOQA: E203
        ]

    permalink = output_file.relative_to(kw["output_folder"])
    title = "Matlab Examples"
    context = {
        "headers": headers,
        "lang": kw["default_lang"],
        "pagekind": ["example"],
        "permalink": str(permalink),
        "title": title,
        "description": title,
    }
    site.render_template("matlab-example-index.tmpl", str(output_file), context)


def render_example(site, kw, in_name, out_name):
    code = highlight(
        in_name.read_bytes(), MatlabLexer(), utils.NikolaPygmentsHTML(in_name.name)
    )

    title = in_name.name
    permalink = out_name.relative_to(kw["output_folder"])
    source_link = permalink.stem  # remove '.html'
    context = {
        "code": code,
        "title": title,
        "permalink": str(permalink),
        "lang": kw["default_lang"],
        "description": title,
        "source_link": source_link,
        "pagekind": ["example"],
    }
    site.render_template("examples.tmpl", str(out_name), context)


class RenderMatlabExamples(Task):

    name = "render_matlab_examples"

    def set_site(self, site):
        """Set Nikola site."""
        # Verify that a Python output folder appears only once in EXAMPLES_FOLDERS
        found_matlab = False
        for source, dest in site.config["EXAMPLES_FOLDERS"].items():
            if "matlab" in dest:
                if found_matlab:
                    self.logger.error(
                        "More than one folder to output Matlab examples was found in "
                        "EXAMPLES_FOLDERS, exiting"
                    )
                else:
                    found_matlab = True
                    self.input_folder = source
                    self.examples_folder = dest

        if not found_matlab:
            self.logger.warn(
                "Didn't find an output folder for Matlab examples in EXAMPLES_FOLDERS"
            )

        return super().set_site(site)

    def gen_tasks(self):
        """Render examples."""
        kw = {
            "default_lang": self.site.config["DEFAULT_LANG"],
            "examples_folders": self.site.config["EXAMPLES_FOLDERS"],
            "output_folder": Path(self.site.config["OUTPUT_FOLDER"]),
            "index_file": self.site.config["INDEX_FILE"],
            "strip_indexes": self.site.config["STRIP_INDEXES"],
        }

        yield self.group_task()

        # When any key or value in the uptodate dictionary changes, the
        # examples pages need to be rebuilt.
        uptodate = {"c": self.site.GLOBAL_CONTEXT}

        for k, v in self.site.GLOBAL_CONTEXT["template_hooks"].items():
            uptodate["||template_hooks|{0}||".format(k)] = v.calculate_deps()

        for k in self.site._GLOBAL_CONTEXT_TRANSLATABLE:
            uptodate[k] = self.site.GLOBAL_CONTEXT[k](kw["default_lang"])

        # save navigation links as dependencies
        uptodate["nav_links"] = uptodate["c"]["navigation_links"](kw["default_lang"])

        uptodate["kw"] = kw

        examples_template_deps = self.site.template_system.template_deps(
            "examples.tmpl"
        )

        index_template_deps = self.site.template_system.template_deps(
            "matlab-example-index.tmpl"
        )
        matlab_examples = list(Path(self.input_folder).resolve().glob("*.m"))
        matlab_headers = {
            "examples": {"name": "Examples", "files": [], "summaries": {}}
        }

        uptodate["d"] = matlab_headers.keys()
        uptodate["f"] = list(map(str, matlab_examples))

        for mat_ex_file in matlab_examples:
            if "tut" in mat_ex_file.name or "test" in mat_ex_file.name:
                continue
            matlab_headers["examples"]["files"].append(mat_ex_file)
            doc = ""
            for line in mat_ex_file.read_text().split("\n"):
                line = line.strip()
                if line.startswith("%"):
                    doc = line.strip("%").strip()
                if doc:
                    break
            # TODO: Warn if example doesn't have a docstring
            if not doc:
                pass
            name = mat_ex_file.stem.replace("_", " ")
            if doc.lower().replace("_", " ").startswith(name):
                # This is too aggressive at removing leading -
                # It also removes from things like "zero-dimensional"
                doc = doc[len(name) :].replace("-", "").strip()  # NOQA: E203
            matlab_headers["examples"]["summaries"][mat_ex_file.name] = doc

            out_name = kw["output_folder"].joinpath(
                self.examples_folder, mat_ex_file.with_suffix(".m.html").name
            )

            yield {
                "basename": self.name,
                "name": str(out_name),
                "file_dep": examples_template_deps + [mat_ex_file],
                "targets": [out_name],
                "actions": [(render_example, [self.site, kw, mat_ex_file, out_name])],
                # This is necessary to reflect changes in blog title,
                # sidebar links, etc.
                "uptodate": [utils.config_changed(uptodate, "matlab_examples:source")],
                "clean": True,
            }

            out_name = kw["output_folder"].joinpath(
                self.examples_folder, mat_ex_file.name
            )
            yield {
                "basename": self.name,
                "name": str(out_name),
                "file_dep": [mat_ex_file],
                "targets": [out_name],
                "actions": [(utils.copy_file, [mat_ex_file, out_name])],
                "clean": True,
            }

        matlab_headers["examples"]["files"] = natsort.natsorted(
            matlab_headers["examples"]["files"], alg=natsort.IC
        )

        out_name = kw["output_folder"].joinpath(self.examples_folder, kw["index_file"])
        yield {
            "basename": self.name,
            "name": str(out_name),
            "file_dep": index_template_deps,
            "targets": [out_name],
            "actions": [
                (
                    render_example_index,
                    [self.site, kw, matlab_headers, out_name],
                )
            ],
            # This is necessary to reflect changes in blog title,
            # sidebar links, etc.
            "uptodate": [utils.config_changed(uptodate, "matlab_examples:folder")],
            "clean": True,
        }
