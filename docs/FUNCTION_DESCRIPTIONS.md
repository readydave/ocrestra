# Function Descriptions

This file explains what each function/method is responsible for.  
Use `FUNCTION_INDEX.md` for the canonical name list and this file for behavior intent.

## `ocr_app/__main__.py`

- `main`: Configure multiprocessing mode and launch the Qt app.

## `ocr_app/themes.py`

- `apply_theme`: Apply selected theme palette/style overrides to `QApplication`.

## `ocr_app/job_runner.py`

### `QueueLogHandler`

- `__init__`: Store queue handle and task id for worker-to-UI log forwarding.
- `emit`: Push formatted log record into multiprocessing queue as a `log` event.

### Module Functions

- `_configure_logging`: Attach file and queue log handlers for a worker.
- `_run_ocr`: Execute OCRmyPDF with configured options for one input/output pair.
- `_should_fallback_to_tmp`: Decide whether mount/permission failure should trigger temp staging fallback.
- `_safe_size`: Return file size with exception-safe fallback.
- `_cleanup_temp_dir`: Remove task temp directory only if it is inside allowed temp root.
- `_sanitize_task_id`: Enforce safe task-id format.
- `_safe_temp_dir`: Ensure worker temp directory resolves under allowed temp root.
- `_is_path_within`: Utility path containment check.
- `_safe_log_file`: Enforce log output path under allowed log root.
- `_safe_output_pdf`: Validate output path safety and reject unsafe/symlink targets.
- `run_ocr_job`: End-to-end worker execution, fallback behavior, metrics collection, and done event emission.

## `ocr_app/ui.py`

### Module Functions

- `_format_bytes`: Human-readable byte formatting.
- `_safe_file_part`: Normalize file-name fragments for safe log file names.
- `run_app`: Build and execute Qt app instance.

### `DropZone`

- `__init__`: Build drag-and-drop widget UI.
- `dragEnterEvent`: Accept drops with URL payloads and enable hover style.
- `dragLeaveEvent`: Clear hover style on drag leave.
- `dropEvent`: Emit local dropped paths and reset hover state.
- `_set_hover`: Toggle hover property and re-polish widget style.

### `MainWindow` (Grouped by Responsibility)

#### App Lifecycle / Setup

- `__init__`: Initialize app state, settings, timers, and startup checks.
- `_build_ui`: Build all widgets/layouts and wire UI-level signals.
- `_build_menus`: Build menu bar and menu actions.
- `_apply_saved_theme`: Apply previously selected theme.
- `set_theme`: Switch and persist theme mode.
- `closeEvent`: Persist settings/state and handle safe shutdown.

#### Settings / Utility

- `_set_combo_data`: Select combo-box item by data value.
- `_check_runtime_dependencies`: Verify external OCR binaries are available.
- `_display_input_path`: Format input path for selected display mode.
- `_on_path_display_changed`: Re-render table input paths when mode changes.

#### Parallelism / Priority

- `_update_parallel_mode_controls`: Enable/disable custom worker spinbox.
- `_resolved_workers`: Resolve effective worker count from presets and limits.
- `_update_parallel_hint`: Show contextual hint for worker/OCR mode.
- `_on_priority_changed`: Persist/apply selected process priority profile.
- `_apply_process_priority`: Apply platform-specific nice/priority and optional ionice behavior.

#### Input Discovery / Queueing

- `_pick_pdfs`: Open file dialog and enqueue selected PDFs.
- `_pick_folder`: Open directory dialog and enqueue discovered PDFs.
- `add_paths`: Validate/enqueue files, create task rows/widgets, enforce queue/file limits.
- `_expand_to_pdfs`: Recursively discover PDFs with dedupe, depth, and discovery safeguards.
- `clear_tasks`: Clear queue/table when no active processing is running.

#### Batch Scheduling / Worker Control

- `start_batch`: Reset run state and start scheduling queued tasks.
- `_schedule_tasks`: Fill available worker slots from queued tasks.
- `_start_task`: Prepare per-task paths/config and launch worker process.
- `_poll_workers`: Periodic worker polling loop and completion/schedule updates.
- `_drain_task_queue`: Drain queued worker events for a specific task.
- `_handle_worker_event`: Route log/status/done event payloads to handlers.
- `_finalize_task`: Complete task lifecycle, finalize status/result/progress, and metrics.
- `_mark_batch_progress`: Track completed count and batch completion state.

#### Cancel / Process Cleanup

- `cancel_task`: Cancel queued/running task and perform cleanup.
- `cancel_selected`: Cancel currently selected rows.
- `cancel_all`: Cancel all queued/running tasks.
- `_close_task_process`: Join/terminate process and close queue handles.
- `_terminate_task_process`: Force-stop worker process if needed.
- `_cleanup_task_files`: Remove safe temp/output artifacts for canceled jobs.

#### Table Selection / Context Actions

- `_selected_task_ids`: Convert selected rows to task IDs.
- `_show_table_context_menu`: Build and execute per-row context menu.
- `_copy_to_clipboard`: Copy value and add confirmation log.
- `_task_id_for_row`: Map table row index to task id.
- `_on_action_button_clicked`: Handle row action button behavior by status.
- `_refresh_action_button`: Update row action label and enabled state.
- `_set_action_button`: Set row action button properties.
- `_set_status`: Update table status cell.
- `_set_result`: Update table result cell/tooltip.
- `_set_log_button`: Configure per-row log button.
- `_set_progress`: Update row progress bar value/format/style.
- `_auto_adjust_table_columns`: Recompute table column widths.
- `resizeEvent`: Trigger responsive column resize on window resize.

#### Logging / Log Views

- `_append_log`: Append line to in-app log buffer/view.
- `_extract_log_level`: Parse severity from formatted log line.
- `_log_entry_visible`: Evaluate log line against current filter settings.
- `_current_selected_task_id`: Return first selected task id.
- `_refresh_log_view`: Rebuild visible log area from filtered log buffer.
- `_on_view_log_clicked`: Open log viewer for row task.
- `_open_log_dialog`: Show per-file log dialog content.
- `open_log_folder`: Open current batch log folder in selected/system manager.

#### OCR Result Intelligence / Progress Estimation

- `_track_task_log_metrics`: Parse worker log lines for skip/HOCR hints.
- `_was_effectively_skipped`: Determine if task should be marked as skipped.
- `_estimate_task_duration`: Estimate task duration from file size for progress pacing.
- `_advance_running_progress`: Advance progress bars heuristically while workers run.
- `_count_pending`: Count queued tasks.
- `_update_batch_progress`: Recompute aggregate batch progress.
- `_update_metrics_labels`: Refresh app/system resource metrics and task peaks.
- `_append_metrics_to_log`: Append GUI-side metrics summary to per-file log.
- `_append_cancel_to_log`: Append cancellation summary to per-file log.

#### File Manager Integration / Safety

- `_open_output_folder`: Open most relevant output folder for a task.
- `_file_manager_options_for_platform`: Return platform-specific file manager options.
- `_file_manager_available`: Check if a manager option is usable.
- `_contains_disallowed_shell_chars`: Detect blocked shell control characters.
- `_validate_custom_file_manager_template`: Validate custom command template safety/usability.
- `_render_custom_file_manager_command`: Render validated custom command for path.
- `_refresh_file_manager_actions`: Update menu enabled/checked state for manager options.
- `_set_file_manager_choice`: Persist selected file manager mode.
- `_set_custom_file_manager_command`: Prompt/save custom manager template.
- `_open_in_file_manager`: Open path via selected manager mode.
- `_open_with_system_default`: Open path via platform system default opener.
- `_run_file_manager_command`: Launch opener command with detached process behavior.

#### Persistence / State Restore

- `_state_file_path`: Resolve queue state file location.
- `_is_secure_state_file`: Validate queue state file permissions/safety.
- `_save_queue_state`: Persist queue + selected options with atomic safe write.
- `_restore_queue_state_prompt`: Prompt and restore queue/settings from saved state.

#### Miscellaneous

- `_is_path_within`: Utility path containment check.
- `_progress_style_for_value`: Select progress-bar color style for percentage band.
- `_resource_health`: Convert numeric resource usage into health label/color.
- `show_usage`: Show in-app usage dialog.
- `show_about`: Show in-app about dialog.
- `_next_output_path`: Compute safe non-colliding output filename.
