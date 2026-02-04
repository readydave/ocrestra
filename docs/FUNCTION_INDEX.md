# Function Index

Auto-generated index of modules, functions, and class methods.

Regenerate with:

```bash
python scripts/gen_function_index.py
```

## `ocr_gui.py`

## `ocr_app/__main__.py`

### Module functions

- `main`

## `ocr_app/config.py`

## `ocr_app/models.py`

### Classes

- `TaskItem`
  - *(no methods)*

## `ocr_app/job_runner.py`

### Module functions

- `_configure_logging`
- `_run_ocr`
- `_should_fallback_to_tmp`
- `_safe_size`
- `_cleanup_temp_dir`
- `_sanitize_task_id`
- `_safe_temp_dir`
- `_is_path_within`
- `_safe_log_file`
- `_safe_output_pdf`
- `run_ocr_job`

### Classes

- `QueueLogHandler`
  - `__init__`
  - `emit`

## `ocr_app/themes.py`

### Module functions

- `apply_theme`

## `ocr_app/ui.py`

### Module functions

- `_format_bytes`
- `_safe_file_part`
- `run_app`

### Classes

- `DropZone`
  - `__init__`
  - `dragEnterEvent`
  - `dragLeaveEvent`
  - `dropEvent`
  - `_set_hover`
- `MainWindow`
  - `__init__`
  - `_build_ui`
  - `_build_menus`
  - `_apply_saved_theme`
  - `set_theme`
  - `_set_combo_data`
  - `_check_runtime_dependencies`
  - `_update_parallel_mode_controls`
  - `_resolved_workers`
  - `_update_parallel_hint`
  - `_on_priority_changed`
  - `_apply_process_priority`
  - `_pick_pdfs`
  - `_pick_folder`
  - `add_paths`
  - `_expand_to_pdfs`
  - `clear_tasks`
  - `start_batch`
  - `_schedule_tasks`
  - `_start_task`
  - `_poll_workers`
  - `_drain_task_queue`
  - `_handle_worker_event`
  - `_finalize_task`
  - `_mark_batch_progress`
  - `cancel_task`
  - `cancel_selected`
  - `cancel_all`
  - `_selected_task_ids`
  - `_show_table_context_menu`
  - `_copy_to_clipboard`
  - `_task_id_for_row`
  - `_is_path_within`
  - `_display_input_path`
  - `_on_path_display_changed`
  - `_close_task_process`
  - `_terminate_task_process`
  - `_cleanup_task_files`
  - `_set_status`
  - `_track_task_log_metrics`
  - `_was_effectively_skipped`
  - `_set_result`
  - `_set_log_button`
  - `_set_progress`
  - `_set_action_button`
  - `_refresh_action_button`
  - `_on_action_button_clicked`
  - `_on_view_log_clicked`
  - `_open_log_dialog`
  - `_open_output_folder`
  - `_file_manager_options_for_platform`
  - `_file_manager_available`
  - `_contains_disallowed_shell_chars`
  - `_validate_custom_file_manager_template`
  - `_render_custom_file_manager_command`
  - `_refresh_file_manager_actions`
  - `_set_file_manager_choice`
  - `_set_custom_file_manager_command`
  - `_open_in_file_manager`
  - `_open_with_system_default`
  - `_run_file_manager_command`
  - `_progress_style_for_value`
  - `_resource_health`
  - `_auto_adjust_table_columns`
  - `resizeEvent`
  - `_estimate_task_duration`
  - `_advance_running_progress`
  - `_count_pending`
  - `_update_batch_progress`
  - `_update_metrics_labels`
  - `_append_metrics_to_log`
  - `_append_cancel_to_log`
  - `open_log_folder`
  - `_state_file_path`
  - `_is_secure_state_file`
  - `_save_queue_state`
  - `_restore_queue_state_prompt`
  - `show_usage`
  - `show_about`
  - `closeEvent`
  - `_append_log`
  - `_extract_log_level`
  - `_log_entry_visible`
  - `_current_selected_task_id`
  - `_refresh_log_view`
  - `_next_output_path`
