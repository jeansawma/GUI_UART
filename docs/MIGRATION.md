# MATLAB → Python migration

The Python application consolidates the original GUIDE windows into a Qt desktop interface. MATLAB is not needed to run it. Original `.m` and `.fig` uploads remain in `legacy/matlab` for reference; the Python application does not execute those files.

## Feature and address map

All addresses below use the **zero-based UART convention**. MATLAB `var` and `Dvar` array indices were one-based.

| Original files / control | Python feature | Wire addresses |
| --- | --- | --- |
| `INIT_Gui.m`, `INIT_Gui.fig` | Port discovery, connect/disconnect, command controls, plot reset, export | Default 115200 8N1 |
| `Plot_Generic.m/.fig` | Variables: 24 read-only values with plot selectors | Row 0, columns 0–23 |
| `Par_Generic.m/.fig` | Parameters: 18 editable values | Row 6, columns 0–17 |
| `Var_Generic.m/.fig` | Control: 24 editable values with plot selectors | Rows 7–8, columns 0–9; row 9, columns 0–3 |
| `OBS_Generic.m/.fig` | Observer: 18 editable values | Row 10, columns 0–17 |
| `Ident_Generic.m/.fig` | Identification: 18 editable values with plot selectors | Row 11, columns 0–9; row 12, columns 0–7 |
| `Others_Generic.m/.fig` | Others: 40 editable values | Rows 2–3, columns 0–19 |
| Start W / Start I / Start Ident | Send value `1` | Row 2, columns 0 / 1 / 2 respectively |
| STOP | Send value `0` to all three start registers | Row 2, columns 0–2 |
| Load Description | Request device-supplied labels | Command `D`, row 0, column 0, value 0 |
| `Plot_Fill_UART.m` | Up to 15 simultaneous signal subscriptions | Subscription rows 13–14; original mirror writes preserved |
| `Serial_receive_fcn.m` | Incremental data, description, plot, and scope decoding | `stx`, `std`, `stv` incoming messages |
| `TxUartCom.m`, `TxRxUartCom.m` | Float32 UART command encoding | `stx` outgoing messages |
| Save Vector / save scopes | MAT and CSV recording export | Local operation |
| `Dessinee.m` | Offline recording viewer and moving-average analysis | Local operation |

Every editable field retains an individual write action; **Write all** retains the original ENTER ALL intent, with a 0.3-second pause after each ten commands. It takes edited values or received live values and validates the entire batch before sending any command. **Use live** explicitly fills editors from device values. Plot selections can be prepared while disconnected and are applied when connected. The original `.fig` field labels are the placeholder `Rs`, rather than meaningful device names. Python uses numbered fallback labels until `std` description packets arrive, then displays the firmware’s names. It does not guess physical quantities or units.

## Wire compatibility

Outgoing commands have a **7-byte header**, followed by a little-endian IEEE-754 float32:

```text
's' 't' 'x'  row  column  command  0  value[4]
```

Ordinary numeric writes use command zero. Description requests use ASCII `D`.

Incoming packets use a distinct **10-byte header** before their payload. This asymmetry comes directly from the receiver’s `i+1` address accesses and `i+7` payload accesses after finding the three-byte marker. The incoming header must not be replaced with the outgoing format merely because both use `stx`.

- `stx`: value arrays for ordinary rows, or streamed float samples plus an int32 device tick for plot channels encoded as rows 200 and above.
- `std`: a description string associated with a row and column.
- `stv`: a scope channel and sample count encoded as three base-100 digits, followed by raw float32 samples.

The decoder buffers incomplete packets across reads and consumes payloads by length. There is no checksum in the supplied protocol. No firmware source or recorded UART stream was supplied, so the inferred reserved-byte layout and device-specific behavior still need validation against hardware.

The default device sample period is 0.0001 seconds; the original plot step is 0.01 seconds and display window is 20 seconds. Incoming device timing is used for acquired plots. Plot subscriptions preserve the original maximum of 15 channels and disabled-slot value `255`.

Serial reads and paced command writes run outside the GUI thread. Rapid selection changes replace superseded routing jobs; samples received while routes are being updated are discarded to avoid assigning them to the wrong signal. STOP cancels pending writes, sends the original three zero commands, and resends the latest signal routing if needed. The protocol has no acknowledgement, so a completed write means bytes were sent, rather than confirmation that firmware applied them. STOP is a software command, not a hardware emergency stop.

## Recordings and analysis

MAT export combines the familiar MATLAB names in one file:

| Variable | Contents |
| --- | --- |
| `tm`, `vplot` | Display sweep time and samples; normally 2001 × 15 values |
| `Tmem`, `vmem` | Nominal recording time and chronological per-channel histories |
| `vscope` | Received scope samples, retaining the original column numbering |
| `valid_lengths`, `scope_lengths` | Actual acquired counts; absent samples use `NaN` |
| `recorded_times` | Actual times for each history channel |
| `signal_addresses`, `signal_labels` | Selected signal metadata |
| `sample_period`, `display_step` | Acquisition timing settings |

CSV exports history samples in long form: `time_s,channel,row,column,label,value`. Channel numbers in CSV are one-based; row/column addresses remain zero-based. CSV contains histories; use MAT to retain scope arrays and the display sweep as well.

The offline viewer accepts Python CSV and MATLAB files containing `Tmem/vmem`, `tm/vplot`, or `vscope`. New MAT files use `recorded_times` to align histories with unequal lengths onto their actual timestamps; legacy files fall back to `Tmem`. Combined exports open the history recording. To view received scopes separately, use **File → Export scopes** and open that scope-only MAT file. **Open recording…** launches the viewer, where **Open** chooses the data file. The viewer supports moving-average smoothing. Its default 51-sample forward window corresponds to MATLAB’s inclusive `i:i+50` slice, with shorter windows at the end. Missing data remains missing. Analysis is local and does not change device registers.

Each history channel retains at most 100,000 samples, discarding its oldest samples when full. Export before resetting local data or ending a session when you need to retain measurements. Offline plots and demo signals are separate from proof of physical UART compatibility.

## Verification boundary

Automated checks can verify packet bytes, fragmented input, field mappings, serial lifecycle behavior, recording round trips, and Qt interactions without hardware. Running the GUI in offscreen mode is useful for those checks:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest
```

Physical validation additionally requires the target device and its serial port: connect at the expected baud rate, refresh descriptions, check observed register values, validate selected plot channels, and compare saved measurements with the device. Do not infer actuator behavior from the generic W/I/Ident captions alone.
