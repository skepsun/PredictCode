"""
main_window
~~~~~~~~~~~

The main menu which is displayed at the start.
"""

from .tk import main_window_view as main_window_view
from . import import_file
import logging, json
import tkinter as _tk
import open_cp.gui.tk.util as util
import open_cp.gui.import_file_model as import_file_model
import open_cp.gui.process_file as process_file
import open_cp.gui.analysis as analysis

class MainWindow():
    def __init__(self, root):
        self._logger = logging.getLogger(__name__)
        self._logger.debug("tkinter version in use: %s", _tk.Tcl().eval('info patchlevel'))
        self._user_quit = False
        self._root = root
        self.init()
        
    def run(self):
        self.view.mainloop()
        
    @property
    def user_quit(self):
        """Has the user quit?"""
        return self._user_quit

    def init(self):
        self._root.resize(30, 20)
        self.view = main_window_view.MainWindowView(self)
        
    def load_csv(self):
        filename = util.ask_open_filename(defaultextension=".csv",
            filetypes = [("csv", "*.csv")],
            title="Please select a CSV file to open")
        if filename is None:
            return
        self.view.destroy()
        import_file.ImportFile(filename).run()
        self.init()

    class CancelException(Exception):
        pass

    def load_session(self, filename=None):
        if filename is None:
            filename = util.ask_open_filename(
                    filetypes = [("JSON session", "*.json")],
                    title="Please select a session file to open")
        if filename is None:
            return
        try:
            model = self._load_session(filename)
        except self.CancelException:
            return
        except Exception as e:
            self._logger.exception("Error loading saved sessions")
            self.view.alert("Failed to read session.\nCause: {}/{}".format(type(e), e))
            return
        self.view.destroy()
        analysis.Analysis(model, self._root).run()
        self.init()

    def _load_session(self, filename):
        with open(filename, "rt") as f:
            data = json.load(f)
        filename = data["filename"]
        parse_settings = import_file_model.ParseSettings.from_dict(data["parse_settings"])
        pf = process_file.ProcessFile(filename, None, parse_settings, self._root, "reload")
        loaded = pf.run()
        if not loaded:
            raise self.CancelException()
        model = analysis.Model.init_from_process_file_model(filename, pf.model)
        model.settings_from_dict(data)
        return model
