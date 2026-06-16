$(document).ready(function () {
    if (typeof WaveDrom === 'undefined') {
        console.error('pl-waveform: WaveDrom library not loaded');
        return;
    }

    bindQuestionInteractions();
    bindTextInputHints();
    bindTextInputValidation();

    WaveDrom.ProcessAll();

    $('.pl-waveform').each(function () {
        initContainer(this);
    });

    var resizeTimer;
    $(window).on('resize', function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function () {
            $('.pl-waveform').each(function () {
                removeOverlays(this, '.pl-waveform-feedback-overlay');
                removeOverlays(this, '.pl-waveform-diff-marker');
                removeOverlays(this, '.pl-waveform-row-score-badge');
                removeOverlays(this, '.pl-waveform-table-score-badge');
                removeOverlays(this, '.pl-waveform-parse-error');
                removeOverlays(this, '.pl-waveform-cell-score-badge');
                removeOverlays(this, '.pl-waveform-input-hint');
                initContainer(this);
            });
        }, 150);
    });
});


// ═══════════════════════════════════════════════════════════════════════════
// Shared helpers
// ═══════════════════════════════════════════════════════════════════════════

var DEFAULT_ALLOWED_VALUES = ['0', '1', 'x'];

/** Normalize a raw value for comparison. */
function normalizeRawValue(value) {
    if (value === null || value === undefined) return '';
    return String(value).trim().toLowerCase();
}

/** Normalize a value against a set of allowed values. */
function normalizeEditableValue(value, allowedValues) {
    var normalized = normalizeRawValue(value);
    if (normalized === '') return '';
    var allowed = allowedValues || DEFAULT_ALLOWED_VALUES;
    for (var idx = 0; idx < allowed.length; idx += 1) {
        if (normalizeRawValue(allowed[idx]) === normalized) {
            return String(allowed[idx]);
        }
    }
    return '';
}

/** Read and normalize the allowed values metadata from a control or row. */
function getAllowedValues(controlOrRow) {
    if (!controlOrRow) return DEFAULT_ALLOWED_VALUES.slice();
    try {
        var raw = controlOrRow.getAttribute('data-allowed-values');
        var parsed = JSON.parse(raw || JSON.stringify(DEFAULT_ALLOWED_VALUES));
        if (!Array.isArray(parsed) || parsed.length === 0) return DEFAULT_ALLOWED_VALUES.slice();
        var seen = {};
        return parsed.map(function (value) {
            return String(value).trim();
        }).filter(function (value) {
            var normalized = normalizeRawValue(value);
            if (!normalized || seen[normalized]) return false;
            seen[normalized] = true;
            return true;
        });
    } catch (e) {
        return DEFAULT_ALLOWED_VALUES.slice();
    }
}

/** Convert SVG-local coordinates into page coordinates. */
function toSVGPixels(svg, el, localX, localY) {
    try {
        var pt = svg.createSVGPoint();
        pt.x = localX;
        pt.y = localY;
        var ctm = el.getCTM();
        if (!ctm) return null;
        var p = pt.matrixTransform(ctm);
        return { x: p.x, y: p.y };
    } catch (e) {
        return null;
    }
}

/** Measure tick and signal positions from the rendered WaveDrom SVG. */
function measureSVGPositions(container, signalNames) {
    var svg = container.querySelector('svg');
    if (!svg) return null;

    var signalSet = new Set(signalNames);
    var tickXMap = {};
    var tickYMap = {};
    var signalYMap = {};

    Array.from(svg.querySelectorAll('text')).forEach(function (t) {
        var txt = t.textContent.trim();

        if (/^\d+$/.test(txt)) {
            try {
                var bbox = t.getBBox();
                var pt = toSVGPixels(svg, t, bbox.x + bbox.width / 2, bbox.y);
                var tickNum = parseInt(txt, 10);
                if (pt && (tickYMap[tickNum] === undefined || pt.y < tickYMap[tickNum])) {
                    tickXMap[tickNum] = pt.x;
                    tickYMap[tickNum] = pt.y;
                }
            } catch (e) { /* skip */ }
            return;
        }

        if (signalSet.has(txt)) {
            try {
                var bbox2 = t.getBBox();
                var pt2 = toSVGPixels(svg, t, bbox2.x, bbox2.y + bbox2.height / 2);
                if (pt2) signalYMap[txt] = pt2.y;
            } catch (e) { /* skip */ }
        }
    });

    var sortedTicks = Object.keys(tickXMap).map(Number).sort(function (a, b) { return a - b; });
    var unitWidth = 60;
    if (sortedTicks.length >= 2) {
        unitWidth = tickXMap[sortedTicks[1]] - tickXMap[sortedTicks[0]];
    }

    container.style.position = 'relative';
    container.style.display = 'inline-block';

    return { tickXMap: tickXMap, signalYMap: signalYMap, sortedTicks: sortedTicks, unitWidth: unitWidth };
}

/** Remove all overlay elements matching a selector from a container. */
function removeOverlays(container, selector) {
    Array.from(container.querySelectorAll(selector)).forEach(function (el) {
        el.remove();
    });
}

/** Parse a slot period, falling back to a default when needed. */
function getSlotPeriod(value, fallbackValue) {
    var parsed = parseFloat(value);
    if (Number.isFinite(parsed) && parsed > 0) {
        return parsed;
    }
    var fallback = parseFloat(fallbackValue);
    if (Number.isFinite(fallback) && fallback > 0) {
        return fallback;
    }
    return 1;
}

/** Compute the center x-position for a slot using measured SVG geometry. */
function getSlotCenterX(measurements, absIndex, period, fallbackCycleNum) {
    if (!measurements || measurements.sortedTicks.length === 0) return null;

    var slotPeriod = getSlotPeriod(period, 1);
    var parsedAbsIndex = Number(absIndex);
    if (Number.isFinite(parsedAbsIndex)) {
        var firstTickX = measurements.tickXMap[measurements.sortedTicks[0]];
        return firstTickX + ((parsedAbsIndex + 0.5) * measurements.unitWidth * slotPeriod);
    }

    var parsedCycleNum = Number(fallbackCycleNum);
    if (!Number.isFinite(parsedCycleNum)) return null;
    var tickX = measurements.tickXMap[parsedCycleNum];
    if (tickX === undefined) return null;
    return tickX + measurements.unitWidth / 2;
}

/** Return the horizontal bounds spanning the measured tick labels. */
function getTickSpanBounds(measurements) {
    if (!measurements || !measurements.sortedTicks || measurements.sortedTicks.length === 0) return null;
    var firstTickX = measurements.tickXMap[measurements.sortedTicks[0]];
    var lastTickX = measurements.tickXMap[measurements.sortedTicks[measurements.sortedTicks.length - 1]];
    return {
        left: firstTickX,
        right: lastTickX + measurements.unitWidth
    };
}

/** Compute the left and right bounds covered by a row's editable cells. */
function computeRowBoundsFromCells(cells, firstTickX, unitWidth, fallbackPeriod) {
    if (!Array.isArray(cells) || cells.length === 0 || !Number.isFinite(firstTickX) || !Number.isFinite(unitWidth)) {
        return null;
    }

    var minLeft = Infinity;
    var maxRight = -Infinity;
    var hasGeometry = false;

    cells.forEach(function (cell) {
        var absIndex = Number(cell && cell.abs_index);
        if (!Number.isFinite(absIndex)) return;

        var period = getSlotPeriod(cell && cell.period, fallbackPeriod);
        var cellWidth = unitWidth * period;
        var left = firstTickX + (absIndex * cellWidth);
        var right = left + cellWidth;

        if (!Number.isFinite(left) || !Number.isFinite(right)) return;
        if (left < minLeft) minLeft = left;
        if (right > maxRight) maxRight = right;
        hasGeometry = true;
    });

    if (!hasGeometry) return null;
    return { left: minLeft, right: maxRight };
}

/** Clear transient feedback styling from a question container. */
function clearQuestionFeedbackState(container) {
    removeOverlays(container, '.pl-waveform-cell-score-badge');

    getQuestionControls(container).forEach(function (control) {
        control.classList.remove('pl-waveform-correct', 'pl-waveform-incorrect', 'pl-waveform-unanswered', 'pl-waveform-control-error', 'pl-waveform-invalid');
    });

    Array.from(container.querySelectorAll('.pl-waveform-editor-row')).forEach(function (row) {
        row.classList.remove('pl-waveform-row-correct', 'pl-waveform-row-incorrect');
    });
}

/** Return the interactive controls currently rendered in a question. */
function getQuestionControls(container) {
    return Array.from(container.querySelectorAll('.pl-waveform-question-control'));
}

/** Return the stable key used to identify a rendered control. */
function getControlKey(control) {
    return control.getAttribute('data-key') || control.getAttribute('name') || '';
}

/** Read the input mode from the container metadata. */
function getInputMode(container) {
    return container.getAttribute('data-input-mode') || 'toggle';
}

/** Read the list of editable signal names from the container metadata. */
function getEditableSignals(container) {
    try {
        return JSON.parse(container.getAttribute('data-editable-signals') || '[]');
    } catch (e) {
        return [];
    }
}

/** Return the per-container map of cells touched by the student. */
function getTouchedCellMap(container) {
    if (!container._plWaveformTouchedCells) {
        container._plWaveformTouchedCells = {};
    }
    return container._plWaveformTouchedCells;
}

/** Mark an editable cell as touched. */
function markCellTouched(container, key) {
    if (!container || !key) return;
    getTouchedCellMap(container)[key] = true;
}

/** Check whether an editable cell has been touched. */
function isCellTouched(container, key) {
    if (!container || !key) return false;
    return !!getTouchedCellMap(container)[key];
}

/** Sync a rendered hit target's metadata and CSS state. */
function updateHitTargetMetadata(target, value) {
    var allowedValues = getAllowedValues(target);
    var normalized = normalizeEditableValue(value, allowedValues);
    var humanValue = normalized || 'unanswered';
    var baseLabel = target.dataset.baseAriaLabel || target.getAttribute('aria-label') || 'Waveform answer';
    target.dataset.baseAriaLabel = baseLabel;
    target.setAttribute('data-value', normalized);
    target.title = normalized
        ? ('Current value: ' + normalized)
        : ('Click to choose ' + allowedValues.join(', '));
    target.setAttribute('aria-label', baseLabel + ': ' + humanValue);
    target.classList.toggle('pl-waveform-cell-hit-unanswered', normalized === '');
    target.classList.toggle('pl-waveform-cell-hit-answered', normalized !== '');
    target.classList.toggle('pl-waveform-cell-hit-touched', target.getAttribute('data-touched') === 'true');
    target.classList.toggle('pl-waveform-cell-hit-x', normalized === 'x');
}

/** Parse JSON from an embedded script tag, falling back on invalid input. */
function parseJsonScript(container, selector, fallback) {
    var script = container.querySelector(selector);
    if (!script) return fallback;
    try {
        return JSON.parse(script.textContent || '');
    } catch (e) {
        console.error('pl-waveform: could not parse ' + selector, e);
        return fallback;
    }
}

/** Deep-clone a JSON-compatible value. */
function cloneJSON(value) {
    return JSON.parse(JSON.stringify(value));
}

/** Return the cached base WaveDrom model for a container. */
function getBaseWaveDromModel(container) {
    if (!container._plWaveformBaseModel) {
        container._plWaveformBaseModel = parseJsonScript(container, '.pl-waveform-base-model', null);
    }
    return container._plWaveformBaseModel ? cloneJSON(container._plWaveformBaseModel) : null;
}

/** Return the cached editable row model list for a container. */
function getEditableRowModels(container) {
    if (!container._plWaveformEditableRows) {
        container._plWaveformEditableRows = parseJsonScript(container, '.pl-waveform-editable-rows', []);
    }
    return container._plWaveformEditableRows;
}

/** Return the embedded WaveDrom script for a container. */
function getWaveDromScript(container) {
    return container.querySelector('script[type="WaveDrom"]');
}

/** Extract the WaveDrom render index from the embedded script id. */
function getWaveDromIndex(container) {
    var script = getWaveDromScript(container);
    if (!script || !script.id) return null;
    var match = script.id.match(/^InputJSON_(\d+)$/);
    return match ? Number(match[1]) : null;
}

/** Re-render a WaveDrom model into the existing output slot. */
function rerenderWaveDrom(container, model) {
    var script = getWaveDromScript(container);
    var index = getWaveDromIndex(container);
    if (!script || index === null || !model) return;

    script.textContent = JSON.stringify(model);
    WaveDrom.RenderWaveForm(index, model, 'WaveDrom_Display_');
}

/** Find a signal entry by name within a WaveDrom model. */
function findWaveDromSignal(model, signalName) {
    if (!model || !Array.isArray(model.signal)) return null;
    for (var idx = 0; idx < model.signal.length; idx += 1) {
        if (model.signal[idx] && model.signal[idx].name === signalName) {
            return model.signal[idx];
        }
    }
    return null;
}

/** Resolve the current value for a rendered cell or hidden input. */
function getControlValue(container, cell, allowedValues) {
    var hiddenInput = document.getElementById('pl-wf-hidden-' + cell.key);
    var control = hiddenInput || getQuestionControls(container).find(function (candidate) {
        return getControlKey(candidate) === cell.key;
    });
    if (!control) return '';
    return normalizeEditableValue(control.value || control.getAttribute('data-value'), allowedValues);
}

/** Apply editable row values back onto the underlying WaveDrom signal. */
function applyEditableRowToSignal(container, signalModel, rowModel) {
    if (!signalModel || !rowModel) return;

    var waveChars = String(rowModel.wave || '').split('');
    var cellsByAbsIndex = {};
    var allowedValues = rowModel.allowed_values || DEFAULT_ALLOWED_VALUES;
    rowModel.cells.forEach(function (cell) {
        cellsByAbsIndex[cell.abs_index] = cell;
    });

    if (rowModel.is_bus) {
        var dataValues = [];
        var prevBusValue = null;
        var fixedData = Array.isArray(signalModel.data) ? signalModel.data.slice() : [];
        var fixedDataIdx = 0;

        waveChars = waveChars.map(function (ch, absIndex) {
            var cell = cellsByAbsIndex[absIndex];
            if (cell) {
                var busValue = getControlValue(container, cell, allowedValues);
                if (busValue === '') {
                    prevBusValue = null;
                    return 'x';
                }
                if (prevBusValue !== null && busValue === prevBusValue) {
                    return '.';
                }
                dataValues.push(busValue);
                prevBusValue = busValue;
                return '=';
            }

            if (ch === '=') {
                // Fixed (non-editable) bus slot: carry original data value through.
                var fixedVal = fixedData[fixedDataIdx++];
                if (fixedVal !== undefined) {
                    if (prevBusValue !== null && fixedVal === prevBusValue) {
                        prevBusValue = fixedVal;
                        return '.';
                    }
                    dataValues.push(fixedVal);
                    prevBusValue = fixedVal;
                } else {
                    prevBusValue = null;
                }
            } else if (ch === 'x') {
                prevBusValue = null;
            }
            return ch;
        });

        signalModel.wave = waveChars.join('');
        if (getInputMode(container) === 'text') delete signalModel.data;
        else if (dataValues.length > 0) signalModel.data = dataValues;
        else delete signalModel.data;
        return;
    }

    var prevValue = null;
    waveChars = waveChars.map(function (ch, absIndex) {
        var cell = cellsByAbsIndex[absIndex];
        if (cell) {
            var value = getControlValue(container, cell, allowedValues) || 'x';
            if (value !== 'x' && value === prevValue) return '.';
            // Reset prevValue on 'x' so the next cell always emits a full
            // character rather than '.'. Without this, a sequence like 0→x→0
            // would produce '0x.' (extending the x) instead of '0x0'.
            prevValue = (value !== 'x') ? value : null;
            return value;
        }

        if (ch !== '.') prevValue = ch;
        return ch;
    });
    signalModel.wave = waveChars.join('');
}

/** Recompute the question WaveDrom model after an edit. */
function updateQuestionWaveDrom(container) {
    if (!container) return;
    var model = getBaseWaveDromModel(container);
    if (!model) return;

    getEditableRowModels(container).forEach(function (rowModel) {
        applyEditableRowToSignal(container, findWaveDromSignal(model, rowModel.signal_name), rowModel);
    });

    rerenderWaveDrom(container, model);
}


// ═══════════════════════════════════════════════════════════════════════════
// Toggle-rendered question editor
// ═══════════════════════════════════════════════════════════════════════════

/** Wire up toggle-mode keyboard and mouse interactions. */
function bindQuestionInteractions() {
    $(document).on('click', '.pl-waveform-cell-hit', function () {
        if (this.disabled) return;
        advanceRenderedCell(this);
    });

    $(document).on('keydown', '.pl-waveform-cell-hit', function (evt) {
        if (this.disabled) return;

        if (evt.key === 'Enter' || evt.key === ' ' || evt.key === 'Spacebar' || evt.key === 'ArrowUp' || evt.key === 'ArrowDown') {
            evt.preventDefault();
            advanceRenderedCell(this);
            return;
        }
        if (evt.key === 'Backspace' || evt.key === 'Delete') {
            evt.preventDefault();
            setRenderedCellValue(this, '');
            return;
        }
        if (evt.key === 'ArrowRight') {
            evt.preventDefault();
            focusAdjacentRenderedCell(this, 1);
            return;
        }
        if (evt.key === 'ArrowLeft') {
            evt.preventDefault();
            focusAdjacentRenderedCell(this, -1);
        }
    });
}

/** Wire up hover and focus hints for text-mode inputs. */
function bindTextInputHints() {
    $(document).on('mouseenter', '.pl-waveform-proxy[data-input-hint]', function () {
        this.dataset.plHintHover = 'true';
        if (this.dataset.plHintMode === 'timed') return;
        showTextInputHint(this);
    });

    $(document).on('focus', '.pl-waveform-proxy[data-input-hint]', function () {
        this.dataset.plHintFocus = 'true';
        showTimedTextInputHint(this, 1000);
    });

    $(document).on('mouseleave', '.pl-waveform-proxy[data-input-hint]', function () {
        delete this.dataset.plHintHover;
        if (this.dataset.plHintMode !== 'timed' && this.dataset.plHintFocus !== 'true') {
            hideTextInputHint(this);
        }
    });

    $(document).on('blur', '.pl-waveform-proxy[data-input-hint]', function () {
        delete this.dataset.plHintFocus;
        if (this.dataset.plHintMode === 'timed') {
            clearTextInputHintTimer(this);
            delete this.dataset.plHintMode;
        }
        if (this.dataset.plHintHover !== 'true') hideTextInputHint(this);
    });
}

/** Enforce allowed-value input handling for text-mode controls. */
function bindTextInputValidation() {
    $(document).on('keydown', '.pl-waveform-proxy[data-allowed-values]', function (evt) {
        if (this.disabled || evt.ctrlKey || evt.metaKey || evt.altKey) return;
        if (isTextInputControlKey(evt.key)) return;
        if (!evt.key || evt.key.length !== 1) return;

        var normalized = normalizeTextInputValue(this, evt.key);
        if (normalized === null) {
            evt.preventDefault();
            rejectTextInputValue(this);
            return;
        }

        evt.preventDefault();
        this.value = normalized;
        this.dispatchEvent(new Event('input', { bubbles: true }));
    });

    $(document).on('paste', '.pl-waveform-proxy[data-allowed-values]', function (evt) {
        if (this.disabled) return;

        var clipboard = evt.originalEvent && evt.originalEvent.clipboardData;
        var pastedText = clipboard ? clipboard.getData('text') : '';
        var normalized = normalizeTextInputValue(this, pastedText);

        evt.preventDefault();
        if (normalized === null) {
            rejectTextInputValue(this);
            return;
        }

        this.value = normalized;
        this.dispatchEvent(new Event('input', { bubbles: true }));
    });

    $(document).on('input', '.pl-waveform-proxy[data-allowed-values]', function () {
        var normalized = normalizeTextInputValue(this, this.value);
        if (normalized === null) {
            this.value = '';
            rejectTextInputValue(this);
            updateQuestionWaveDrom(this.closest('.pl-waveform'));
            return;
        }
        if (this.value !== normalized) {
            this.value = normalized;
        }
        updateQuestionWaveDrom(this.closest('.pl-waveform'));
    });
}

/** Return true when a key should be treated as text-input navigation. */
function isTextInputControlKey(key) {
    return [
        'Backspace',
        'Delete',
        'Tab',
        'Enter',
        'Escape',
        'ArrowLeft',
        'ArrowRight',
        'ArrowUp',
        'ArrowDown',
        'Home',
        'End'
    ].indexOf(key) !== -1;
}

/** Normalize a text input value or reject it if it is not allowed. */
function normalizeTextInputValue(input, value) {
    if (normalizeRawValue(value) === '') return '';
    var normalized = normalizeEditableValue(value, getAllowedValues(input));
    return normalized === '' ? null : normalized;
}

/** Briefly flag a rejected text input value. */
function rejectTextInputValue(input) {
    input.classList.add('pl-waveform-input-rejected');
    showTimedTextInputHint(input, 1000);
    clearTimeout(input._plWaveformRejectTimer);
    input._plWaveformRejectTimer = setTimeout(function () {
        input.classList.remove('pl-waveform-input-rejected');
    }, 700);
}

/** Show a hint for a limited amount of time. */
function showTimedTextInputHint(input, delayMs) {
    input.dataset.plHintMode = 'timed';
    showTextInputHint(input);
    clearTextInputHintTimer(input);
    input._plWaveformHintTimer = setTimeout(function () {
        hideTextInputHint(input);
        delete input.dataset.plHintMode;
    }, delayMs);
}

/** Render a text-input hint near the focused control. */
function showTextInputHint(input) {
    var hintText = input.getAttribute('data-input-hint');
    var container = input.closest('.pl-waveform');
    if (!hintText || !container) return;

    hideTextInputHint(input);

    var hint = document.createElement('div');
    hint.className = 'pl-waveform-input-hint';
    hint.textContent = hintText;

    var inputRect = input.getBoundingClientRect();
    var containerRect = container.getBoundingClientRect();
    hint.style.left = Math.round(inputRect.left - containerRect.left + inputRect.width / 2) + 'px';
    hint.style.top = Math.round(inputRect.top - containerRect.top - 6) + 'px';

    container.appendChild(hint);
    input._plWaveformInputHint = hint;
}

/** Clear the pending text-input hint timer. */
function clearTextInputHintTimer(input) {
    clearTimeout(input._plWaveformHintTimer);
    input._plWaveformHintTimer = null;
}

/** Remove any visible hint for a text input. */
function hideTextInputHint(input) {
    clearTextInputHintTimer(input);
    if (input._plWaveformInputHint) {
        input._plWaveformInputHint.remove();
        input._plWaveformInputHint = null;
    }
}

/** Build the toggle-mode overlay editor. */
function buildToggleEditor(container) {
    var editorLayer = container.querySelector('.pl-waveform-editor-layer');
    if (!editorLayer) return;

    editorLayer.innerHTML = '';

    var editableSignals = getEditableSignals(container);
    var m = measureSVGPositions(container, editableSignals);
    if (!m || m.sortedTicks.length === 0) return;

    var baseRows = getEditableRowModels(container);
    var firstTickX = m.tickXMap[m.sortedTicks[0]];
    var rowHeight = 34;

    baseRows.forEach(function (baseRow) {
        var sigY = m.signalYMap[baseRow.signal_name];
        if (sigY === undefined) return;

        var rowElement = createToggleRowElement(container, baseRow, firstTickX, m.unitWidth, rowHeight, sigY);
        editorLayer.appendChild(rowElement);
    });
}

/** Create a toggle-mode row and its interactive cell buttons. */
function createToggleRowElement(container, rowModel, firstTickX, unitWidth, rowHeight, sigY) {
    var cellPeriod = rowModel.period || 1;
    var rowWidth = rowModel.wave_length * unitWidth * cellPeriod;
    var rowElement = document.createElement('div');
    rowElement.className = 'pl-waveform-editor-row';
    rowElement.setAttribute('data-signal', rowModel.signal_name);
    rowElement.setAttribute('data-allowed-values', JSON.stringify(rowModel.allowed_values || DEFAULT_ALLOWED_VALUES));
    rowElement.style.left = Math.round(firstTickX) + 'px';
    rowElement.style.top = Math.round(sigY - rowHeight / 2) + 'px';
    rowElement.style.width = Math.round(rowWidth) + 'px';
    rowElement.style.height = rowHeight + 'px';

    rowModel.cells.forEach(function (cell) {
        if (!cell.editable) return;

        var hitTarget = document.createElement('button');
        hitTarget.type = 'button';
        hitTarget.className = 'pl-waveform-question-control pl-waveform-cell-hit';
        hitTarget.setAttribute('data-key', cell.key);
        hitTarget.setAttribute('data-signal', rowModel.signal_name);
        hitTarget.setAttribute('data-cycle', cell.cycle_num);
        hitTarget.setAttribute('data-abs-index', cell.abs_index);
        hitTarget.setAttribute('data-hidden-input-id', 'pl-wf-hidden-' + cell.key);
        hitTarget.setAttribute('data-allowed-values', JSON.stringify(rowModel.allowed_values || DEFAULT_ALLOWED_VALUES));
        hitTarget.setAttribute('aria-label', cell.aria_label);
        hitTarget.style.left = Math.round(cell.abs_index * unitWidth * cellPeriod) + 'px';
        hitTarget.style.top = '0';
        hitTarget.style.width = Math.round(unitWidth * cellPeriod) + 'px';
        hitTarget.style.height = rowHeight + 'px';

        var hiddenInput = document.getElementById('pl-wf-hidden-' + cell.key);
        if (hiddenInput && hiddenInput.disabled) {
            hitTarget.disabled = true;
        }

        var initialValue = hiddenInput ? hiddenInput.value : cell.value;
        if (normalizeEditableValue(initialValue, rowModel.allowed_values || ['0', '1', 'x']) !== '') {
            markCellTouched(container, cell.key);
        }
        if (isCellTouched(container, cell.key)) {
            hitTarget.setAttribute('data-touched', 'true');
        }
        updateHitTargetMetadata(hitTarget, initialValue);
        rowElement.appendChild(hitTarget);
    });

    return rowElement;
}

// ── Text-mode: editable row background bands ───────────────────────────────
// Mirrors the toggle-mode row band logic.  Each editable signal row gets a
// .pl-waveform-editor-row div that spans its full editable width, giving the
// same blue-tinted visual cue as toggle mode without any interactive elements.
/** Build non-interactive background bands for text-mode editing. */
function buildTextEditorRowBands(container) {
    var editorLayer = container.querySelector('.pl-waveform-editor-layer');
    if (!editorLayer) return;

    editorLayer.innerHTML = '';

    var editableSignals = getEditableSignals(container);
    var m = measureSVGPositions(container, editableSignals);
    if (!m || m.sortedTicks.length === 0) return;

    var baseRows = getEditableRowModels(container);
    var tickSpan = getTickSpanBounds(m);
    if (!tickSpan) return;
    var rowHeight = 34;

    baseRows.forEach(function (baseRow) {
        var sigY = m.signalYMap[baseRow.signal_name];
        if (sigY === undefined) return;
        var rowBounds = computeRowBoundsFromCells(baseRow.cells, tickSpan.left, m.unitWidth, baseRow.period) || tickSpan;

        var band = document.createElement('div');
        band.className = 'pl-waveform-editor-row';
        band.setAttribute('data-signal', baseRow.signal_name);
        band.style.left = Math.round(rowBounds.left) + 'px';
        band.style.top = Math.round(sigY - rowHeight / 2) + 'px';
        band.style.width = Math.round(rowBounds.right - rowBounds.left) + 'px';
        band.style.height = rowHeight + 'px';
        editorLayer.appendChild(band);
    });
}



/** Advance a toggle cell to the next allowed state. */
function advanceRenderedCell(control) {
    var container = control.closest('.pl-waveform');
    var key = getControlKey(control);
    var touched = isCellTouched(container, key);
    var allowedValues = getAllowedValues(control);
    var states = touched ? allowedValues.slice() : [''].concat(allowedValues);
    var current = normalizeEditableValue(control.getAttribute('data-value'), allowedValues);
    var idx = states.indexOf(current);
    if (idx === -1) idx = touched ? -1 : 0;
    setRenderedCellValue(control, states[(idx + 1) % states.length], { markTouched: true });
}


/** Update a toggle cell and synchronize the hidden input state. */
function setRenderedCellValue(control, value, options) {
    var opts = options || {};
    var allowedValues = getAllowedValues(control);
    var container = control.closest('.pl-waveform');
    var key = getControlKey(control);
    if (opts.markTouched && container && key) {
        markCellTouched(container, key);
    }

    var touched = isCellTouched(container, key);
    var normalized = normalizeEditableValue(value, allowedValues);
    if (touched && normalized === '') {
        var current = normalizeEditableValue(control.getAttribute('data-value'), allowedValues);
        normalized = current || String(allowedValues[0] || '');
    }

    var hiddenInput = document.getElementById(control.getAttribute('data-hidden-input-id'));
    if (hiddenInput && !hiddenInput.disabled) {
        hiddenInput.value = normalized;
    }
    control.setAttribute('data-touched', touched ? 'true' : 'false');
    updateHitTargetMetadata(control, normalized);

    if (container) {
        updateQuestionWaveDrom(container);
    }
}

/** Move focus to the next or previous toggle cell in the row. */
function focusAdjacentRenderedCell(control, delta) {
    var row = control.closest('.pl-waveform-editor-row');
    if (!row) return;

    var cells = Array.from(row.querySelectorAll('.pl-waveform-cell-hit'));
    var idx = cells.indexOf(control);
    if (idx === -1) return;

    var next = cells[idx + delta];
    if (next) {
        next.focus();
    }
}


// ═══════════════════════════════════════════════════════════════════════════
// Question panel: legacy text input positioning
// ═══════════════════════════════════════════════════════════════════════════

/** Position text-mode inputs over the matching waveform slots. */
function positionTextInputs(container) {
    var editableSignals = getEditableSignals(container);
    var m = measureSVGPositions(container, editableSignals);
    if (!m || m.sortedTicks.length === 0) return;

    var inputH = 22;

    Array.from(container.querySelectorAll('.pl-waveform-proxy')).forEach(function (inp) {
        var sigName = inp.getAttribute('data-signal');
        var sigY = m.signalYMap[sigName];
        var slotPeriod = getSlotPeriod(inp.getAttribute('data-period'), 1);
        var slotWidth = m.unitWidth * slotPeriod;
        var inputW = Math.max(24, Math.min(44, Math.round(slotWidth - 8)));
        var centreX = getSlotCenterX(
            m,
            inp.getAttribute('data-abs-index'),
            inp.getAttribute('data-period'),
            inp.getAttribute('data-cycle')
        );

        if (sigY === undefined || centreX === null) {
            inp.style.position = 'relative';
            inp.style.visibility = 'visible';
            inp.style.display = 'inline-block';
            inp.style.margin = '2px';
            return;
        }

        inp.style.position = 'absolute';
        inp.style.left = Math.round(centreX - inputW / 2) + 'px';
        inp.style.top = Math.round(sigY - inputH / 2) + 'px';
        inp.style.width = inputW + 'px';
        inp.style.height = inputH + 'px';
        inp.style.margin = '0';
        inp.style.visibility = 'visible';
        inp.style.display = 'inline-block';
    });
}


// ═══════════════════════════════════════════════════════════════════════════
// Container init
// ═══════════════════════════════════════════════════════════════════════════

/** Initialize a waveform container for its current panel state. */
function initContainer(container) {
    var panel = container.getAttribute('data-panel') || '';
    var inputMode = getInputMode(container);

    if (panel === 'question') {
        if (inputMode === 'toggle') {
            buildToggleEditor(container);
        } else {
            positionTextInputs(container);
            buildTextEditorRowBands(container);
        }

        if (container.hasAttribute('data-cell-scores')) {
            renderQuestionScoreBadges(container);
        }
    } else {
        if (container.hasAttribute('data-feedback-rows')) {
            renderRowOverlays(container);
        } else if (container.hasAttribute('data-feedback')) {
            renderFeedbackOverlays(container);
        }
    }

    if (container.hasAttribute('data-diff')) {
        renderDiffMarkers(container);
    }
    if (container.hasAttribute('data-parse-errors')) {
        renderParseErrorOverlays(container);
    }
}


// ═══════════════════════════════════════════════════════════════════════════
// Shared overlay rendering
// ═══════════════════════════════════════════════════════════════════════════

/** Append a cell-level overlay marker at the computed waveform position. */
function appendCellOverlay(container, m, signalName, cycleNum, className, absIndex, period) {
    var sigY = m.signalYMap[signalName];
    var centreX = getSlotCenterX(m, absIndex, period, cycleNum);
    if (sigY === undefined || centreX === null) return;

    var overlay = document.createElement('div');
    overlay.className = 'pl-waveform-feedback-overlay ' + className;

    var overlayW = Math.max(18, m.unitWidth * getSlotPeriod(period, 1) * 0.85);
    var overlayH = 28;

    overlay.style.left = Math.round(centreX - overlayW / 2) + 'px';
    overlay.style.top = Math.round(sigY - overlayH / 2) + 'px';
    overlay.style.width = Math.round(overlayW) + 'px';
    overlay.style.height = overlayH + 'px';

    container.appendChild(overlay);
}


// ═══════════════════════════════════════════════════════════════════════════
// Submission panel: feedback overlays
// ═══════════════════════════════════════════════════════════════════════════

/** Render cell-level feedback overlays for submission mode. */
function renderFeedbackOverlays(container) {
    var editableSignals = getEditableSignals(container);
    var feedback = [];
    try {
        feedback = JSON.parse(container.getAttribute('data-feedback') || '[]');
    } catch (e) { return; }

    var m = measureSVGPositions(container, editableSignals);
    if (!m) return;

    feedback.forEach(function (cell) {
        if (cell.correct) {
            appendCellOverlay(
                container,
                m,
                cell.signal_name,
                cell.cycle_num,
                'pl-waveform-feedback-correct',
                cell.abs_index,
                cell.period
            );
        } else if (cell.incorrect) {
            appendCellOverlay(
                container,
                m,
                cell.signal_name,
                cell.cycle_num,
                'pl-waveform-feedback-incorrect',
                cell.abs_index,
                cell.period
            );
        }
    });
}


// ═══════════════════════════════════════════════════════════════════════════
// Submission panel: row-level overlays (feedback="row")
// ═══════════════════════════════════════════════════════════════════════════

/** Render row-level feedback overlays for submission mode. */
function renderRowOverlays(container) {
    var editableSignals = getEditableSignals(container);
    var feedback = [];
    try {
        feedback = JSON.parse(container.getAttribute('data-feedback-rows') || '[]');
    } catch (e) { return; }

    var m = measureSVGPositions(container, editableSignals);
    if (!m || m.sortedTicks.length === 0) return;

    var rowStatus = {};
    feedback.forEach(function (cell) {
        if (!rowStatus[cell.signal_name]) {
            rowStatus[cell.signal_name] = { allCorrect: true };
        }
        if (cell.incorrect) {
            rowStatus[cell.signal_name].allCorrect = false;
        }
    });

    var tickSpan = getTickSpanBounds(m);
    if (!tickSpan) return;

    editableSignals.forEach(function (sigName) {
        var sigY = m.signalYMap[sigName];
        var status = rowStatus[sigName];
        if (sigY === undefined || !status) return;
        var rowCells = feedback.filter(function (cell) { return cell.signal_name === sigName; });
        var rowBounds = computeRowBoundsFromCells(rowCells, tickSpan.left, m.unitWidth, 1) || tickSpan;

        var overlay = document.createElement('div');
        overlay.className = 'pl-waveform-feedback-overlay ' +
            (status.allCorrect ? 'pl-waveform-feedback-correct' : 'pl-waveform-feedback-incorrect');

        var overlayH = 28;
        overlay.style.left = Math.round(rowBounds.left) + 'px';
        overlay.style.top = Math.round(sigY - overlayH / 2) + 'px';
        overlay.style.width = Math.round(rowBounds.right - rowBounds.left) + 'px';
        overlay.style.height = overlayH + 'px';

        container.appendChild(overlay);
    });
}


// ═══════════════════════════════════════════════════════════════════════════
// Answer panel: diff markers
// ═══════════════════════════════════════════════════════════════════════════

/** Render answer-vs-student diff markers. */
function renderDiffMarkers(container) {
    var editableSignals = getEditableSignals(container);
    var diffCells = [];
    try {
        diffCells = JSON.parse(container.getAttribute('data-diff') || '[]');
    } catch (e) { return; }

    var m = measureSVGPositions(container, editableSignals);
    if (!m) return;

    diffCells.forEach(function (cell) {
        if (!cell.differs) return;

        var sigY = m.signalYMap[cell.signal_name];
        var centreX = getSlotCenterX(m, cell.abs_index, cell.period, cell.cycle_num);
        if (sigY === undefined || centreX === null) return;

        var marker = document.createElement('div');
        marker.className = 'pl-waveform-diff-marker';
        marker.textContent = 'yours: ' + cell.student_value;
        marker.title = 'You answered ' + cell.student_value + ', correct is ' + cell.correct_value;

        marker.style.left = Math.round(centreX - 25) + 'px';
        marker.style.top = Math.round(sigY + 14) + 'px';

        container.appendChild(marker);
    });
}


// ═══════════════════════════════════════════════════════════════════════════
// Question panel: parse error overlays
// ═══════════════════════════════════════════════════════════════════════════

/** Render parse-error badges over invalid question controls. */
function renderParseErrorOverlays(container) {
    var parseErrors = {};
    try {
        parseErrors = JSON.parse(container.getAttribute('data-parse-errors') || '{}');
    } catch (e) { return; }

    getQuestionControls(container).forEach(function (control) {
        control.classList.remove('pl-waveform-control-error');
    });

    if (Object.keys(parseErrors).length === 0) return;

    var BADGE = 14;
    var containerRect = container.getBoundingClientRect();

    getQuestionControls(container).forEach(function (control) {
        var key = getControlKey(control);
        if (!parseErrors[key]) return;

        control.classList.add('pl-waveform-control-error');
        var r = control.getBoundingClientRect();
        var relL = r.left - containerRect.left;
        var relT = r.top - containerRect.top;

        var badge = document.createElement('div');
        badge.className = 'pl-waveform-parse-error';
        badge.textContent = '!';
        badge.title = parseErrors[key];
        // Position: half overlapping the top-right corner of the input
        badge.style.left = Math.round(relL + r.width - BADGE / 2) + 'px';
        badge.style.top = Math.round(relT - BADGE / 2) + 'px';
        badge.style.width = BADGE + 'px';
        badge.style.height = BADGE + 'px';

        container.appendChild(badge);
    });
}


// ═══════════════════════════════════════════════════════════════════════════
// Question panel: score badges after submission (per feedback mode)
// ═══════════════════════════════════════════════════════════════════════════

/** Render score badges for question or submission feedback. */
function renderQuestionScoreBadges(container) {
    var editableSignals = getEditableSignals(container);
    var feedback = container.getAttribute('data-feedback') || 'cell';
    var inputMode = getInputMode(container);
    var cellScores = [];

    try {
        cellScores = JSON.parse(container.getAttribute('data-cell-scores') || '[]');
    } catch (e) { return; }

    if (cellScores.length === 0) return;
    clearQuestionFeedbackState(container);

    if (feedback === 'cell') {
        if (inputMode === 'toggle') {
            var toggleScoreMap = {};
            cellScores.forEach(function (cell) {
                toggleScoreMap[cell.signal_name + '|' + cell.cycle_num] = cell;
            });

            Array.from(container.querySelectorAll('.pl-waveform-cell-hit')).forEach(function (control) {
                var mapKey = control.getAttribute('data-signal') + '|' + control.getAttribute('data-cycle');
                var cell = toggleScoreMap[mapKey];
                if (!cell) return;

                control.classList.remove('pl-waveform-correct', 'pl-waveform-incorrect', 'pl-waveform-unanswered', 'pl-waveform-control-error', 'pl-waveform-invalid');
                if (cell.correct) control.classList.add('pl-waveform-correct');
                else if (cell.invalid) control.classList.add('pl-waveform-invalid');
                else if (cell.incorrect) control.classList.add('pl-waveform-incorrect');
                else if (cell.unanswered) control.classList.add('pl-waveform-unanswered');

                var badge = document.createElement('span');
                var badgeStateClass = cell.correct
                    ? 'pl-waveform-cell-score-correct'
                    : 'pl-waveform-cell-score-incorrect';
                badge.className = 'pl-waveform-cell-score-badge pl-waveform-cell-score-badge-corner ' + badgeStateClass;
                badge.textContent = cell.correct ? '\u2713' : '\u2717';
                badge.title = cell.correct ? 'correct' : (cell.invalid ? (cell.invalid_message || 'invalid') : (cell.unanswered ? 'unanswered' : 'incorrect'));
                badge.setAttribute('aria-hidden', 'true');
                control.appendChild(badge);
            });
            return;
        }
        // Text-mode keeps direct input tinting plus a small status badge.
        var BADGE = 14;
        var containerRect = container.getBoundingClientRect();
        var scoreMap = {};
        cellScores.forEach(function (cell) {
            scoreMap[cell.signal_name + '|' + cell.cycle_num] = cell;
        });

        Array.from(container.querySelectorAll('.pl-waveform-proxy')).forEach(function (inp) {
            var mapKey = inp.getAttribute('data-signal') + '|' + inp.getAttribute('data-cycle');
            var cell = scoreMap[mapKey];
            inp.classList.remove('pl-waveform-correct', 'pl-waveform-incorrect', 'pl-waveform-unanswered', 'pl-waveform-control-error', 'pl-waveform-invalid');
            if (!cell) return;
            if (cell.correct) inp.classList.add('pl-waveform-correct');
            else if (cell.invalid) inp.classList.add('pl-waveform-invalid');
            else if (cell.incorrect) inp.classList.add('pl-waveform-incorrect');
            else if (cell.unanswered) inp.classList.add('pl-waveform-unanswered');

            var r = inp.getBoundingClientRect();
            var relL = r.left - containerRect.left;
            var relT = r.top - containerRect.top;

            var badge = document.createElement('div');
            badge.className = 'pl-waveform-cell-score-badge ' +
                (cell.correct
                    ? 'pl-waveform-cell-score-correct'
                    : 'pl-waveform-cell-score-incorrect');
            badge.textContent = cell.correct ? '\u2713' : '\u2717';
            badge.setAttribute('aria-label', cell.correct ? 'correct' : (cell.invalid ? (cell.invalid_message || 'invalid') : (cell.unanswered ? 'unanswered' : 'incorrect')));
            badge.title = cell.correct ? 'correct' : (cell.invalid ? (cell.invalid_message || 'invalid') : (cell.unanswered ? 'unanswered' : 'incorrect'));
            badge.style.left = Math.round(relL + r.width - BADGE / 2) + 'px';
            badge.style.top = Math.round(relT - BADGE / 2) + 'px';
            badge.style.width = BADGE + 'px';
            badge.style.height = BADGE + 'px';
            container.appendChild(badge);
        });
        return;
    }

    if (feedback === 'row') {
        var mRow = measureSVGPositions(container, editableSignals);
        if (!mRow || mRow.sortedTicks.length === 0) return;

        var rowData = {};
        cellScores.forEach(function (cell) {
            if (!rowData[cell.signal_name]) rowData[cell.signal_name] = { total: 0, correct: 0 };
            rowData[cell.signal_name].total += 1;
            if (cell.correct) rowData[cell.signal_name].correct += 1;
        });

        var tickSpan = getTickSpanBounds(mRow);
        if (!tickSpan) return;
        var rowH = 28;

        editableSignals.forEach(function (sigName) {
            var sigY = mRow.signalYMap[sigName];
            var rd = rowData[sigName];
            if (sigY === undefined || !rd) return;
            var rowCells = cellScores.filter(function (cell) { return cell.signal_name === sigName; });
            var rowBounds = computeRowBoundsFromCells(rowCells, tickSpan.left, mRow.unitWidth, 1) || tickSpan;

            var allCorrect = rd.correct === rd.total;
            var strip = document.createElement('div');
            strip.className = 'pl-waveform-feedback-overlay ' +
                (allCorrect ? 'pl-waveform-feedback-correct' : 'pl-waveform-feedback-incorrect');
            strip.style.left = Math.round(rowBounds.left) + 'px';
            strip.style.top = Math.round(sigY - rowH / 2) + 'px';
            strip.style.width = Math.round(rowBounds.right - rowBounds.left) + 'px';
            strip.style.height = rowH + 'px';
            container.appendChild(strip);

            var pill = document.createElement('div');
            pill.className = 'pl-waveform-row-score-badge ' +
                (allCorrect ? 'pl-waveform-row-score-correct' : 'pl-waveform-row-score-incorrect');
            pill.textContent = rd.correct + '/' + rd.total + ' correct';
            pill.title = rd.correct + ' of ' + rd.total + ' correct';
            pill.style.left = Math.round(rowBounds.right + 8) + 'px';
            pill.style.top = Math.round(sigY - 14) + 'px';
            container.appendChild(pill);
        });
        return;
    }

    if (feedback === 'table') {
        var mTable = measureSVGPositions(container, editableSignals);
        if (!mTable || mTable.sortedTicks.length === 0) return;

        var total = cellScores.length;
        var correct = cellScores.filter(function (cell) { return cell.correct; }).length;
        var pct = total > 0 ? Math.round(100 * correct / total) : 0;
        var yVals = editableSignals
            .map(function (signalName) { return mTable.signalYMap[signalName]; })
            .filter(function (y) { return y !== undefined; });
        var midY = yVals.length > 0 ? yVals.reduce(function (a, b) { return a + b; }, 0) / yVals.length : 40;
        var lastTick = mTable.tickXMap[mTable.sortedTicks[mTable.sortedTicks.length - 1]];
        var rightEdgeTable = lastTick + mTable.unitWidth;

        var badge = document.createElement('div');
        badge.className = 'pl-waveform-table-score-badge';
        if (pct === 100) badge.classList.add('pl-waveform-table-score-correct');
        else badge.classList.add('pl-waveform-table-score-incorrect');

        badge.textContent = correct + '/' + total + ' correct';
        badge.title = pct + '% correct';
        badge.style.left = Math.round(rightEdgeTable + 10) + 'px';
        badge.style.top = Math.round(midY - 14) + 'px';
        container.appendChild(badge);
    }
}
