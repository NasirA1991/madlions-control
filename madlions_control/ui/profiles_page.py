"""Tuning profiles, full backups and presets."""

from __future__ import annotations

import json
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, Gtk  # noqa: E402

from .. import config, profiles
from .widgets import Page, Section, button, label, separator


class ProfilesPage(Page):
    title = "Profiles"
    subtitle = "Tuning profiles for everyday use, full backups for recovery."

    def __init__(self, window) -> None:
        super().__init__(window, max_width=1040)
        self._full_busy = False
        self._build()

    def _build(self) -> None:
        save = button("Save tuning profile", icon="list-add-symbolic", suggested=True)
        save.connect("clicked", lambda _b: self._save_dialog())
        self.add(self.header(save))

        presets = Section(
            "Presets",
            "Sensible starting points. Applying one never writes persistent onboard data.",
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
            "Saved tuning profiles",
            "Actuation, rapid trigger, lighting and switches. Stored as readable JSON.",
            trailing=self._import_button(),
        )
        self.saved_rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.saved.add(self.saved_rows)
        self.add(self.saved)

        backups = Section(
            "Backups",
            "A full backup also contains the keymap, macros and advanced bindings. "
            "Restoring it writes those persistent sections immediately.",
        )
        self.full_button = button("Create full backup", icon="document-save-symbolic")
        self.full_button.connect("clicked", lambda _b: self._full_backup())
        self.snapshot_button = button("Tuning snapshot", icon="document-save-symbolic",
                                      flat=True)
        self.snapshot_button.connect("clicked", lambda _b: self._snapshot())
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.append(self.full_button)
        actions.append(self.snapshot_button)
        self.backup_label = label("", "tiny muted")
        actions.append(self.backup_label)
        backups.add(actions)
        self.backup_rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        backups.add(self.backup_rows)
        self.add(backups)

        safety = Section(
            "Save to the keyboard",
            "Applying a tuning profile is volatile. This button persists actuation, "
            "rapid trigger and lighting.",
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
        self._rebuild_saved()
        self._rebuild_backups()

    def _rebuild_saved(self) -> None:
        while child := self.saved_rows.get_first_child():
            self.saved_rows.remove(child)
        saved = profiles.list_profiles()
        if not saved:
            self.saved_rows.append(
                label("No saved tuning profiles yet. Use “Save tuning profile”.",
                      "muted small")
            )
            return
        for index, profile in enumerate(saved):
            widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            widget.add_css_class("list-row")
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            text.set_hexpand(True)
            text.append(label(profile.name, "row-title"))
            detail = profiles.profile_summary(profile)
            if profile.is_full:
                detail += " · full backup"
            text.append(label(detail, "row-sub", wrap=True))
            text.append(label(profiles.section_summary(profile), "tiny muted", wrap=True))
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
            delete.connect("clicked", lambda _b, p=profile: self._delete(p, profile_dir=True))
            widget.append(apply)
            widget.append(export)
            widget.append(delete)
            self.saved_rows.append(widget)
            if index != len(saved) - 1:
                self.saved_rows.append(separator())

    def _rebuild_backups(self) -> None:
        while child := self.backup_rows.get_first_child():
            self.backup_rows.remove(child)
        directory = config.backups_dir()
        entries: list[tuple[Path, profiles.Profile]] = []
        if directory.is_dir():
            for path in sorted(directory.glob("*.json"), reverse=True):
                try:
                    entries.append((path, profiles.Profile.load(path)))
                except (OSError, ValueError):
                    continue
        if not entries:
            self.backup_rows.append(label(
                "No backups yet. A tuning snapshot is also created automatically on "
                "the first connection.",
                "muted small",
            ))
            return
        for index, (path, profile) in enumerate(entries[:10]):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.add_css_class("list-row")
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            text.set_hexpand(True)
            text.append(label(profile.name, "row-title"))
            text.append(label(profiles.section_summary(profile), "row-sub", wrap=True))
            text.append(label(
                ("Full backup" if profile.is_full else "Tuning snapshot")
                + " · " + time.strftime("%Y-%m-%d %H:%M", time.localtime(profile.created)),
                "tiny muted",
            ))
            row.append(text)
            restore = button("Restore", flat=True)
            restore.connect("clicked", lambda _b, p=profile: self.window.apply_profile(p))
            export = Gtk.Button()
            export.set_child(Gtk.Image.new_from_icon_name("document-export-symbolic"))
            export.set_tooltip_text("Export backup")
            export.add_css_class("flat")
            export.connect("clicked", lambda _b, p=profile: self._export(p))
            delete = Gtk.Button()
            delete.set_child(Gtk.Image.new_from_icon_name("user-trash-symbolic"))
            delete.set_tooltip_text("Delete backup file")
            delete.add_css_class("flat")
            delete.connect("clicked", lambda _b, p=profile: self._delete(p, profile_dir=False))
            row.append(restore)
            row.append(export)
            row.append(delete)
            self.backup_rows.append(row)
            if index != min(len(entries), 10) - 1:
                self.backup_rows.append(separator())

    # -- actions -----------------------------------------------------------
    def _save_dialog(self) -> None:
        if not self.window.state.connected:
            self.window.notify("Connect a keyboard first.")
            return
        dialog = Adw.AlertDialog(
            heading="Save tuning profile",
            body=(
                "Captures actuation, rapid trigger, lighting and switches. "
                "It does not include the keymap, macros or advanced bindings — "
                "use “Create full backup” for a complete restore point."
            ),
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
            try:
                profile = profiles.Profile.capture(
                    self.window.state,
                    name.get_text().strip() or "Profile",
                    description.get_text().strip(),
                    full=False,
                )
                profile.save()
            except (OSError, ValueError) as exc:
                self.window.notify(f"Could not save profile: {exc}")
                return
            self.window.notify(f"Saved “{profile.name}”.")
            self._rebuild()

        dialog.connect("response", response)
        dialog.present(self.window)

    def _full_backup(self) -> None:
        if not self.window.state.connected:
            self.window.notify("Connect a keyboard first.")
            return
        if self._full_busy:
            return
        self._full_busy = True
        self.full_button.set_sensitive(False)
        self.backup_label.set_text("Reading every section…")

        def job(device):
            return profiles.full_backup(device)

        def done(result):
            self._full_busy = False
            self.full_button.set_sensitive(True)
            profile, path = result
            self.backup_label.set_text(f"Saved {path.name}")
            self.window.notify(f"Full backup “{profile.name}” saved.")
            self._rebuild()

        def error(exc):
            self._full_busy = False
            self.full_button.set_sensitive(True)
            self.backup_label.set_text("")
            self.window.notify(f"Full backup failed: {exc}")

        self.window.worker.submit(job, callback=done, error=error, description="full backup")

    def _snapshot(self) -> None:
        state = self.window.state
        if not state.connected:
            self.window.notify("Connect a keyboard first.")
            return
        path = profiles.auto_backup(state)
        if path:
            self.backup_label.set_text(f"Saved {path.name}")
            self.window.notify("Tuning snapshot created.")
            self._rebuild()
        else:
            self.window.notify("Nothing to snapshot yet.")

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
                try:
                    Path(path).write_text(
                        json.dumps(profile.to_json(), indent=2), encoding="utf-8"
                    )
                except OSError as exc:
                    self.window.notify(f"Could not export: {exc}")
                    return
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
                profile = profiles.Profile.load(Path(path))
                profile.save(config.backups_dir() if profile.is_full else None)
            except (OSError, ValueError) as exc:
                self.window.notify(f"Could not import: {exc}")
                return
            self.window.notify(f"Imported “{profile.name}”.")
            self._rebuild()

        dialog.open(self.window, None, done)

    def _delete(self, profile, *, profile_dir: bool) -> None:
        dialog = Adw.AlertDialog(
            heading=f"Delete “{profile.name}”?",
            body="The file is removed. The keyboard is not changed.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def response(_dialog, response_id):
            if response_id != "delete":
                return
            directory = config.profiles_dir() if profile_dir else config.backups_dir()
            for path in directory.glob("*.json"):
                try:
                    if profiles.Profile.load(path).name == profile.name:
                        path.unlink()
                        break
                except (OSError, ValueError):
                    continue
            self._rebuild()

        dialog.connect("response", response)
        dialog.present(self.window)
