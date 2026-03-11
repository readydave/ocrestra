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
- `_build_ocr_command`
- `_easyocr_plugin_autoregistered`
- `_is_easyocr_duplicate_registration_error`
- `_run_ocr_command`
- `_is_gpu_related_failure`
- `_is_input_file_error`
- `_format_ocr_error`
- `_run_with_gpu_retry`
- `_run_ocr`
- `_should_fallback_to_tmp`
- `_safe_size`
- `_cleanup_temp_dir`
- `_sanitize_task_id`
- `_safe_temp_dir`
- `_is_path_within`
- `_safe_log_file`
- `_has_symlink_segment`
- `_safe_output_pdf`
- `_ensure_safe_output_dir`
- `_copy_file_to_fd`
- `_install_output_pdf_generic`
- `_install_output_pdf_posix`
- `_install_output_pdf`
- `run_ocr_job`

### Classes

- `QueueLogHandler`
  - `__init__`
  - `emit`
- `OCRCommandError`
  - `__init__`

## `ocr_app/themes.py`

### Module functions

- `_system_font_stack`
- `_resolve_primary_accent`
- `_theme_tokens`
- `build_qss`
- `apply_theme`

## `ocr_app/ui.py`

### Module functions

- `_resolve_app_icon_path`
- `_set_windows_app_user_model_id`
- `_linux_desktop_entry_available`
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
- `ArrowComboBox`
  - `__init__`
  - `paintEvent`
- `CollapsibleSection`
  - `__init__`
  - `_on_toggled`
- `QueueEmptyStateOverlay`
  - `__init__`
  - `_clamp`
  - `_update_for_size`
  - `resizeEvent`
- `MainWindow`
  - `__init__`
  - `_build_ui`
  - `_build_menus`
  - `_apply_saved_theme`
  - `set_theme`
  - `_reset_to_defaults`
  - `_set_combo_data`
  - `_build_option_row`
  - `_easyocr_plugin_available`
  - `_check_runtime_dependencies`
  - `_update_parallel_mode_controls`
  - `_resolved_workers`
  - `_update_parallel_hint`
  - `_on_gpu_toggle_changed`
  - `_on_optimize_size_changed`
  - `_on_priority_changed`
  - `_apply_process_priority`
  - `_pick_pdfs`
  - `_pick_folder`
  - `_prompt_folder_scan_mode`
  - `add_paths`
  - `_expand_to_pdfs`
  - `clear_tasks`
  - `start_batch`
  - `_confirm_force_ocr_risk`
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
  - `_query_nvidia_gpu_metrics`
  - `_auto_adjust_table_columns`
  - `_set_stats_visible`
  - `_update_splitter_orientation`
  - `_sync_empty_state_overlay`
  - `eventFilter`
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
  - `_is_secure_state_dir`
  - `_ensure_secure_state_dir`
  - `_is_secure_state_file`
  - `_unfinished_queue_paths`
  - `_save_queue_state`
  - `_restore_queue_state_prompt`
  - `_prompt_exit_queue_action`
  - `show_usage`
  - `show_about`
  - `closeEvent`
  - `_append_log`
  - `_extract_log_level`
  - `_log_entry_visible`
  - `_current_selected_task_id`
  - `_refresh_log_view`
  - `_next_output_path`
