"""Named profiles, presets and safe snapshots."""

from __future__ import annotations

import json
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from .. import config, profiles
from .widgets import Page, Section, button, label, separator, toast


class ProfilesPage(Page):
    title = "Profiles"
    subtitle = "Whole-keyboard setups that are easy to try and easy to undo."

    def __init__(self, window) -> None:
        super().__init__(window, max_width=1040)
        self._build()

    def _build(self) -> None:
        save = button("Save current", icon="list-add-symbolic", suggested=True)
        save.connect("clicked", lambda _b: self._save_dialog())
        self.add(self.header(save))

        presets = Section(
            "Presets",
            "Sensible starting points. Applying one never writes to flash.",
        )
        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_homogeneous(True)
        flow.set_max_children_per_line(3)
        flow.set_min_children_per_line(1)
        flow.set_column_spacing(8)
        flow.set_row_spacing(8)
        for preset in profiles.presets():
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            card.add_css_class("profile-card")
            card.append(label(preset.name, "card-title"))
            card.append(label(preset.description, "card-sub", wrap=True))
            card.append(label(profiles.profile_summary(preset), "tiny muted"))
            apply = button("Apply", flat=True)
            apply.set_halign(Gtk.Align.START)
            apply.connect("clicked", lambda _b, p=preset: self.window.apply_profile(p))
            card.append(apply)
            child = Gtk.FlowBoxChild()
            child.set_child(card)
            flow.append(child)
        presets.add(flow)
        self.add(presets)

        self.saved = Section(
            "Saved profiles",
            "Stored as readable JSON files in your home directory.",
            trailing=self._import_button(),
        )
        self.saved_rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.saved.add(self.saved_rows)
        self.add(self.saved)

        safety = Section(
            "Save to the keyboard",
            "Applying a profile is volatile. This button is the only thing that "
            "persists actuation and rapid trigger to the keyboard's own memory.",
        )
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        text = label(
            "Flash writes are limited in number, so Madlions Control only does one "
            "when you explicitly ask for it.",
            "row-sub", wrap=True,
        )
        text.set_hexpand(True)
        row.append(text)
        save_button = button("Save now", icon="document-save-symbolic")
        save_button.connect("clicked", lambda _b: self.window.save_to_keyboard())
        row.append(save_button)
        safety.add(row)
        self.add(safety)

        backup = Section("Backups", "A snapshot of the current keyboard that can be imported again.")
        backup_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        create = button("Create backup", icon="document-save-symbolic")
        create.connect("clicked", lambda _b: self._backup())
        backup_row.append(create)
        self.backup_label = label("", "tiny muted")
        backup_row.append(self.backup_label)
        backup.add(backup_row)
        self.add(backup)

    def _import_button(self) -> Gtk.Button:
        widget = button("Import", icon="folder-open-symbolic", flat=True)
        widget.connect("clicked", lambda _b: self._import())
        return widget

    # -- state -------------------------------------------------------------
    def on_state(self, state) -> None:
        self._rebuild()

    def on_show(self) -> None:
        state = self.window.state
        if state.connected and not state.colors:
            self.window.worker.refresh_colors(
                callback=lambda loaded: self.window.set_state_local(loaded)
            )
        self._rebuild()

    def _rebuild(self) -> None:
        while child := self.saved_rows.get_first_child():
            self.saved_rows.remove(child)
        saved = profiles.list_profiles()
        if not saved:
            self.saved_rows.append(
                label("No saved profiles yet. Use “Save current” to create one.", "muted small")
            )
            return
        for index, profile in enumerate(saved):
            widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            widget.add_css_class("list-row")
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            text.set_hexpand(True)
            text.append(label(profile.name, "row-title"))
            text.append(label(profiles.profile_summary(profile), "row-sub", wrap=True))
            widget.append(text)
            apply = button("Apply", flat=True)
            apply.connect("clicked", lambda _b, p=profile: self.window.apply_profile(p))
            export = Gtk.Button()
            export.set_child(Gtk.Image.new_from_icon_name("document-export-symbolic"))
            export.set_tooltip_text("Export profile")
            export.add_css_class("flat")
            export.connect("clicked", lambda _b, p=profile: self._export(p))
            delete = Gtk.Button()
            delete.set_child(Gtk.Image.new_from_icon_name("user-trash-symbolic"))
            delete.set_tooltip_text("Delete profile")
            delete.add_css_class("flat")
            delete.connect("clicked", lambda _b, p=profile: self._delete(p))
            widget.append(apply)
            widget.append(export)
            widget.append(delete)
            self.saved_rows.append(widget)
            if index != len(saved) - 1:
                self.saved_rows.append(separator())

    # -- actions -----------------------------------------------------------
    def _save_dialog(self) -> None:
        if not self.window.state.connected:
            self.window.notify("Connect a keyboard first.")
            return
        dialog = Adw.AlertDialog(
            heading="Save current profile",
            body="The current actuation, rapid trigger, lighting and switches are captured.",
        )
        form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        name = Gtk.Entry()
        name.set_placeholder_text("Profile name")
        name.set_text(time.strftime("Profile %Y-%m-%d"))
        description = Gtk.Entry()
        description.set_placeholder_text("Description (optional)")
        form.append(name)
        form.append(description)
        dialog.set_extra_child(form)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("save")
        dialog.set_close_response("cancel")

        def response(_dialog, response_id):
            if response_id != "save":
                return
            profile = profiles.Profile.capture(
                self.window.state, name.get_text().strip() or "Profile",
                description.get_text().strip(),
            )
            profile.save()
            self.window.notify(f"Saved “{profile.name}”.")
            self._rebuild()

        dialog.connect("response", response)
        dialog.present(self.window)

    def _export(self, profile) -> None:
        dialog = Gtk.FileDialog()
        dialog.set_title(f"Export {profile.name}")
        dialog.set_initial_name(f"{profiles.safe_filename(profile.name)}.json")

        def done(source, result):
            try:
                file = source.save_finish(result)
            except Exception:
                return
            path = file.get_path()
            if path:
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(profile.to_json(), handle, indent=2)
                self.window.notify("Profile exported.")

        dialog.save(self.window, None, done)

    def _import(self) -> None:
        dialog = Gtk.FileDialog()
        dialog.set_title("Import profile")
        filters = Gtk.FileFilter()
        filters.set_name("Madlions profiles")
        filters.add_pattern("*.json")
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(filters)
        dialog.set_filters(store)

        def done(source, result):
            try:
                file = source.open_finish(result)
            except Exception:
                return
            path = file.get_path()
            if not path:
                return
            try:
                profile = profiles.Profile.load(path)
                profile.save()
            except Exception as exc:  # noqa: BLE001
                self.window.notify(f"Could not import: {exc}")
                return
            self.window.notify(f"Imported “{profile.name}”.")
            self._rebuild()

        dialog.open(self.window, None, done)

    def _delete(self, profile) -> None:
        dialog = Adw.AlertDialog(
            heading=f"Delete “{profile.name}”?",
            body="The profile file is removed. The keyboard is not changed.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def response(_dialog, response_id):
            if response_id != "delete":
                return
            path = config.profiles_dir() / f"{profiles.safe_filename(profile.name)}.json"
            try:
                path.unlink()
            except OSError:
                pass
            self._rebuild()

        dialog.connect("response", response)
        dialog.present(self.window)

    def _backup(self) -> None:
        state = self.window.state
        if not state.connected:
            self.window.notify("Connect a keyboard first.")
            return
        path = profiles.auto_backup(state)
        if path:
            self.backup_label.set_text(f"Saved {path.name}")
            self.window.notify("Backup created.")
        else:
            self.window.notify("Nothing to back up yet.")
