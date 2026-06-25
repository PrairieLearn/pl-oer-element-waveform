$(document).ready(function () {
    if (typeof WaveDrom === 'undefined') {
        console.error('pl-waveform: WaveDrom library not loaded');
        return;
    }

    bindQuestionInteractions();
    bindTextInputHints();
    bindTextInputValidation();

    renderWaveDromScripts();

    $('.pl-waveform').each(function () {
        initContainer(this);
    });

    var resizeTimer;
    $(window).on('resize', function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function () {
            $('.pl-waveform').each(function () {
                reinitContainer(this);
            });
        }, 150);
    });

    $(document).on('shown.bs.collapse shown.bs.tab shown.bs.modal', function (event) {
        initVisibleWaveforms(event.target);
    });
});


// ═══════════════════════════════════════════════════════════════════════════
// Shared helpers
// ═══════════════════════════════════════════════════════════════════════════

var DEFAULT_ALLOWED_VALUES = ['0', '1', 'x'];
var DEFAULT_SIGNAL_LABEL_HEIGHT = 22;
var SIGNAL_ROW_VERTICAL_PADDING = 16;
var FEEDBACK_STATE_CLASSES = 'pl-waveform-correct pl-waveform-incorrect pl-waveform-unanswered pl-waveform-control-error pl-waveform-invalid'.split(' ');
var GENERATED_OVERLAY_SELECTOR = '.pl-waveform-feedback-overlay, .pl-waveform-diff-marker, .pl-waveform-row-score-badge, .pl-waveform-element-score-badge, .pl-waveform-parse-error, .pl-waveform-parse-error-summary, .pl-waveform-cell-score-badge, .pl-waveform-input-hint';

/** Normalize a raw value for comparison. */
function normalizeRawValue(value) {
    if (value === null || value === undefined) return '';
    return String(value).trim().toLowerCase();
}

/** Normalize a value against a set of allowed values. */
function normalizeEditableValue(value, allowedValues, busWidth) {
    var normalized = normalizeRawValue(value);
    if (normalized === '') return '';
    var allowed = allowedValues || DEFAULT_ALLOWED_VALUES;
    if (busWidth) {
        var displayed = String(value).trim();
        if (displayed.length !== busWidth) return '';
        var chars = [];
        for (var charIdx = 0; charIdx < displayed.length; charIdx += 1) {
            var canonical = normalizeEditableValue(displayed.charAt(charIdx), allowed, null);
            if (canonical === '') return '';
            chars.push(canonical);
        }
        return chars.join('');
    }
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
        var parsed = controlOrRow.allowed_values;
        if (!Array.isArray(parsed) && typeof controlOrRow.getAttribute === 'function') {
            parsed = JSON.parse(controlOrRow.getAttribute('data-allowed-values') || JSON.stringify(DEFAULT_ALLOWED_VALUES));
        }
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

/** Read a positive fixed bus width from a control or row model when present. */
function getBusWidth(controlOrRow) {
    if (!controlOrRow) return null;
    var raw = controlOrRow.bus_width;
    if (raw === undefined && typeof controlOrRow.getAttribute === 'function') {
        raw = controlOrRow.getAttribute('data-bus-width');
    }
    var width = parseInt(raw, 10);
    return Number.isFinite(width) && width > 0 ? width : null;
}

/** Convert element-local coordinates into SVG viewport coordinates. */
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

/** Convert SVG-local coordinates into container-local coordinates. */
function toContainerPixels(svg, container, el, localX, localY) {
    var pt = toSVGPixels(svg, el, localX, localY);
    if (!pt) return null;

    var svgRect = svg.getBoundingClientRect();
    var containerRect = container.getBoundingClientRect();
    return {
        x: pt.x + svgRect.left - containerRect.left,
        y: pt.y + svgRect.top - containerRect.top
    };
}

/** Measure tick and signal positions from the rendered WaveDrom SVG. */
function measureSVGPositions(container, signalNames) {
    var svg = container.querySelector('svg');
    if (!svg) return null;

    var containerRect = container.getBoundingClientRect();
    var signalSet = new Set(signalNames);
    var tickXMap = {};
    var tickYMap = {};
    var signalYMap = {};
    var signalBoundsMap = {};

    Array.from(svg.querySelectorAll('text')).forEach(function (t) {
        var txt = t.textContent.trim();

        if (/^\d+$/.test(txt)) {
            try {
                var bbox = t.getBBox();
                var pt = toContainerPixels(svg, container, t, bbox.x + bbox.width / 2, bbox.y);
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
                var pt2 = toContainerPixels(svg, container, t, bbox2.x, bbox2.y + bbox2.height / 2);
                if (pt2) signalYMap[txt] = pt2.y;

                var labelRect = t.getBoundingClientRect();
                var labelBounds = {
                    top: labelRect.top - containerRect.top,
                    bottom: labelRect.bottom - containerRect.top
                };
                var lane = t.closest('[id^="wavelane_"]');
                if (lane && !signalBoundsMap[txt]) {
                    var laneBox = lane.getBBox();
                    var top = toContainerPixels(svg, container, lane, laneBox.x, laneBox.y);
                    var bottom = toContainerPixels(svg, container, lane, laneBox.x, laneBox.y + laneBox.height);
                    if (top && bottom) {
                        labelBounds.top = Math.min(labelBounds.top, top.y, bottom.y);
                        labelBounds.bottom = Math.max(labelBounds.bottom, top.y, bottom.y);
                    }
                }
                if (!signalBoundsMap[txt]) {
                    signalBoundsMap[txt] = {
                        top: labelBounds.top,
                        bottom: labelBounds.bottom,
                        height: labelBounds.bottom - labelBounds.top
                    };
                }
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

    return {
        tickXMap: tickXMap,
        signalYMap: signalYMap,
        signalBoundsMap: signalBoundsMap,
        sortedTicks: sortedTicks,
        unitWidth: unitWidth
    };
}

/** Remove all overlay elements matching a selector from a container. */
function removeOverlays(container, selector) {
    Array.from(container.querySelectorAll(selector)).forEach(function (el) {
        el.remove();
    });
}

/** Remove all generated overlays from a waveform container. */
function clearGeneratedOverlays(container) {
    removeOverlays(container, GENERATED_OVERLAY_SELECTOR);
}

/** Clear feedback state classes from a question control. */
function clearFeedbackClasses(control) {
    control.classList.remove.apply(control.classList, FEEDBACK_STATE_CLASSES);
}

/** Return whether a waveform can currently be measured. */
function isMeasurableWaveform(container) {
    if (!container || !container.isConnected) return false;

    var rect = container.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return false;

    var svg = container.querySelector('svg');
    if (!svg) return true;

    var svgRect = svg.getBoundingClientRect();
    return svgRect.width > 0 && svgRect.height > 0;
}

/** Mark a hidden waveform for initialization once it becomes visible. */
function deferUntilVisible(container) {
    container.setAttribute('data-pl-waveform-pending-init', 'true');

    if (typeof ResizeObserver !== 'undefined' && !container._plWaveformResizeObserver) {
        container._plWaveformResizeObserver = new ResizeObserver(function () {
            // Avoid re-rendering on overlay size changes after the hidden panel has initialized.
            if (container.getAttribute('data-pl-waveform-pending-init') === 'true' &&
                isMeasurableWaveform(container)) {
                reinitContainer(container);
            }
        });
        container._plWaveformResizeObserver.observe(container);
    }
}

/** Initialize all measurable waveforms inside a root node. */
function initVisibleWaveforms(root) {
    var scope = root || document;
    var containers = [];

    if (scope.classList && scope.classList.contains('pl-waveform')) {
        containers.push(scope);
    }
    containers = containers.concat(Array.from(scope.querySelectorAll ? scope.querySelectorAll('.pl-waveform') : []));

    containers.forEach(function (container) {
        if (container.getAttribute('data-pl-waveform-pending-init') === 'true' || isMeasurableWaveform(container)) {
            reinitContainer(container);
        }
    });
}

/** Clear generated UI and initialize a waveform from current geometry. */
function reinitContainer(container) {
    clearGeneratedOverlays(container);
    initContainer(container);
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

/** Return the measured vertical bounds for a signal row. */
function getSignalRowBounds(measurements, signalName, fallbackY, fallbackHeight) {
    var minHeight = fallbackHeight || 34;
    var bounds = measurements && measurements.signalBoundsMap && measurements.signalBoundsMap[signalName];
    if (bounds && Number.isFinite(bounds.top) && Number.isFinite(bounds.bottom) && bounds.bottom > bounds.top) {
        var paddedHeight = bounds.height > DEFAULT_SIGNAL_LABEL_HEIGHT
            ? Math.max(minHeight, bounds.height + SIGNAL_ROW_VERTICAL_PADDING)
            : minHeight;
        var center = (bounds.top + bounds.bottom) / 2;
        return {
            top: center - paddedHeight / 2,
            bottom: center + paddedHeight / 2,
            height: paddedHeight
        };
    }

    return {
        top: fallbackY - minHeight / 2,
        bottom: fallbackY + minHeight / 2,
        height: minHeight
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

/** Clear transient feedback styling from a waveform container. */
function clearScoreFeedbackState(container) {
    removeOverlays(container, '.pl-waveform-cell-score-badge');

    getQuestionControls(container).forEach(function (control) {
        clearFeedbackClasses(control);
    });

    Array.from(container.querySelectorAll('.pl-waveform-editor-row')).forEach(function (row) {
        row.classList.remove('pl-waveform-row-correct', 'pl-waveform-row-incorrect');
    });
}

/** Return the interactive controls currently rendered in a question. */
function getQuestionControls(container) {
    return Array.from(container.querySelectorAll('.pl-waveform-question-control'));
}

/** Return the visible text represented by a WaveDrom name value. */
function nameText(value) {
    if (value === null || value === undefined) return '';
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
        return String(value);
    }
    if (!Array.isArray(value)) return '';

    var children = value;
    if (value.length > 0 && typeof value[0] === 'string') {
        children = value.slice(1);
    }
    if (children.length > 0 && Object.prototype.toString.call(children[0]) === '[object Object]') {
        children = children.slice(1);
    }
    return children.map(nameText).join('');
}

/** Add WaveDrom label-width metadata for formatted array names. */
function prepareWaveDromName(name) {
    if (!Array.isArray(name)) return;

    var text = nameText(name);
    Object.defineProperty(name, 'textWidth', {
        value: Math.max(1, text.length * 8),
        configurable: true
    });
}

/** Add WaveDrom-compatible width metadata to all signal names in a model. */
function prepareWaveDromModel(model) {
    if (!model || !Array.isArray(model.signal)) return model;
    model.signal.forEach(function (signal) {
        if (signal && typeof signal === 'object' && !Array.isArray(signal)) {
            prepareWaveDromName(signal.name);
        }
    });
    return model;
}

/** Render the WaveDrom scripts owned by this element. */
function renderWaveDromScripts() {
    $('.pl-waveform script[type="WaveDrom"]').each(function (idx) {
        var script = this;
        var displayId = 'WaveDrom_Display_' + idx;
        script.id = 'InputJSON_' + idx;

        if (!document.getElementById(displayId)) {
            var display = document.createElement('div');
            display.id = displayId;
            script.parentNode.insertBefore(display, script);
        }

        try {
            var model = prepareWaveDromModel(JSON.parse(script.textContent || '{}'));
            var container = script.closest('.pl-waveform');
            if (container && !container._plWaveformBaseModel) {
                container._plWaveformBaseModel = cloneJSON(model);
            }
            WaveDrom.RenderWaveForm(idx, model, 'WaveDrom_Display_');
        } catch (e) {
            console.error('pl-waveform: could not render WaveDrom model', e);
        }
    });
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

/** Sync a rendered hit target's metadata and CSS state. */
function updateHitTargetMetadata(target, value) {
    var allowedValues = getAllowedValues(target);
    var normalized = normalizeEditableValue(value, allowedValues, getBusWidth(target));
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
        container._plWaveformBaseModel = parseJsonScript(container, 'script[type="WaveDrom"]', null);
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

/** Re-render a WaveDrom model into the existing output slot. */
function rerenderWaveDrom(container, model) {
    var script = container.querySelector('script[type="WaveDrom"]');
    var match = script && script.id && script.id.match(/^InputJSON_(\d+)$/);
    if (!script || !match || !model) return;

    script.textContent = JSON.stringify(model);
    WaveDrom.RenderWaveForm(Number(match[1]), prepareWaveDromModel(model), 'WaveDrom_Display_');
}

/** Find a signal entry by display name within a WaveDrom model. */
function findWaveDromSignal(model, signalName) {
    if (!model || !Array.isArray(model.signal)) return null;
    for (var idx = 0; idx < model.signal.length; idx += 1) {
        if (model.signal[idx] && JSON.stringify(model.signal[idx].name) === JSON.stringify(signalName)) {
            return model.signal[idx];
        }
    }
    return null;
}

/** Resolve the current value for a rendered cell or hidden input. */
function getControlValue(container, cell, allowedValues, busWidth) {
    var hiddenInput = document.getElementById('pl-wf-hidden-' + cell.key);
    var control = hiddenInput || getQuestionControls(container).find(function (candidate) {
        return getControlKey(candidate) === cell.key;
    });
    if (!control) return '';
    return normalizeEditableValue(control.value || control.getAttribute('data-value'), allowedValues, busWidth);
}

/** Apply editable row values back onto the underlying WaveDrom signal. */
function applyEditableRowToSignal(container, signalModel, rowModel) {
    if (!signalModel || !rowModel) return;

    signalModel.wave = rowModel.wave;
    if (Array.isArray(rowModel.data) && rowModel.data.length > 0) {
        signalModel.data = rowModel.data.slice();
    } else {
        delete signalModel.data;
    }

    var waveChars = String(rowModel.wave || '').split('');
    var cellsByAbsIndex = {};
    var allowedValues = getAllowedValues(rowModel);
    var busWidth = getBusWidth(rowModel);
    rowModel.cells.forEach(function (cell) {
        cellsByAbsIndex[cell.abs_index] = cell;
    });

    if (rowModel.is_bus) {
        var dataValues = [];
        var prevBusValue = null;
        var fixedData = Array.isArray(rowModel.data) ? rowModel.data.slice() : [];
        var fixedDataIdx = 0;

        waveChars = waveChars.map(function (ch, absIndex) {
            var cell = cellsByAbsIndex[absIndex];
            if (cell) {
                var busValue = getControlValue(container, cell, allowedValues, busWidth);
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
            var value = getControlValue(container, cell, allowedValues, busWidth) || 'x';
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
        applyEditableRowToSignal(container, findWaveDromSignal(model, rowModel.display_name || rowModel.signal_name), rowModel);
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

        var start = this.selectionStart === null ? this.value.length : this.selectionStart;
        var end = this.selectionEnd === null ? this.value.length : this.selectionEnd;
        var candidate = this.value.slice(0, start) + evt.key + this.value.slice(end);
        if (!isAllowedTextInputPrefix(this, candidate)) {
            evt.preventDefault();
            rejectTextInputValue(this);
        }
    });

    $(document).on('paste', '.pl-waveform-proxy[data-allowed-values]', function (evt) {
        if (this.disabled) return;

        var clipboard = evt.originalEvent && evt.originalEvent.clipboardData;
        var pastedText = clipboard ? clipboard.getData('text') : '';
        var start = this.selectionStart === null ? this.value.length : this.selectionStart;
        var end = this.selectionEnd === null ? this.value.length : this.selectionEnd;
        var candidate = this.value.slice(0, start) + pastedText + this.value.slice(end);

        if (!isAllowedTextInputPrefix(this, candidate)) {
            evt.preventDefault();
            rejectTextInputValue(this);
        }
    });

    $(document).on('input', '.pl-waveform-proxy[data-allowed-values]', function () {
        if (!isAllowedTextInputPrefix(this, this.value)) {
            rejectTextInputValue(this);
        } else if (hasValidControlValue(this)) {
            clearTextInputParseError(this, true);
        }
        updateQuestionWaveDrom(this.closest('.pl-waveform'));
    });

    $(document).on('blur', '.pl-waveform-proxy[data-allowed-values]', function () {
        normalizeTextInputOnFocusChange(this);
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

/** Return whether a text input value is blank, complete, or an allowed prefix. */
function isAllowedTextInputPrefix(input, value) {
    var normalizedRaw = normalizeRawValue(value);
    if (normalizedRaw === '') return true;
    var allowedValues = getAllowedValues(input);
    var busWidth = getBusWidth(input);
    if (busWidth) {
        var displayed = String(value).trim();
        if (displayed.length > busWidth) return false;
        for (var charIdx = 0; charIdx < displayed.length; charIdx += 1) {
            if (normalizeEditableValue(displayed.charAt(charIdx), allowedValues, null) === '') return false;
        }
        return true;
    }
    for (var idx = 0; idx < allowedValues.length; idx += 1) {
        if (normalizeRawValue(allowedValues[idx]).indexOf(normalizedRaw) === 0) {
            return true;
        }
    }
    return false;
}

/** Canonicalize a text input value after the student leaves the field. */
function normalizeTextInputOnFocusChange(input) {
    if (!input || input.disabled) return;

    var normalizedRaw = normalizeRawValue(input.value);
    if (normalizedRaw === '') {
        input.value = '';
        updateQuestionWaveDrom(input.closest('.pl-waveform'));
        return;
    }

    var normalized = normalizeEditableValue(input.value, getAllowedValues(input), getBusWidth(input));
    if (normalized === '') {
        showTextInputParseError(input, invalidTextInputMessage(input));
        updateQuestionWaveDrom(input.closest('.pl-waveform'));
        return;
    }

    clearTextInputParseError(input, true);
    if (input.value !== normalized) {
        input.value = normalized;
        updateQuestionWaveDrom(input.closest('.pl-waveform'));
    }
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

/** Return the invalid-value message for a text input. */
function invalidTextInputMessage(input) {
    var busWidth = getBusWidth(input);
    var label = input.getAttribute('data-allowed-values-label') || getAllowedValues(input).join(', ');
    if (label === 'hexadecimal' || label === 'binary') {
        var expected = busWidth ? (busWidth + ' ' + label + ' characters') : label;
        return 'Invalid value. Expected ' + expected + '.';
    }
    if (busWidth) return 'Invalid value. Expected ' + busWidth + ' characters using ' + label + '.';
    return 'Invalid value. Expected one of: ' + label + '.';
}

/** Return whether a control currently contains a complete valid value. */
function hasValidControlValue(control) {
    return normalizeEditableValue(
        control.value || control.getAttribute('data-value'),
        getAllowedValues(control),
        getBusWidth(control)
    ) !== '';
}

/** Return an existing parse-error badge for a text input. */
function getTextInputParseErrorBadge(input) {
    var container = input && input.closest('.pl-waveform');
    var key = input && getControlKey(input);
    if (!container || !key) return null;
    return Array.from(container.querySelectorAll('.pl-waveform-parse-error')).find(function (badge) {
        return badge.getAttribute('data-key') === key;
    }) || null;
}

/** Remove persistent parse-error styling from a text input. */
function clearTextInputParseError(input, clearInvalid) {
    if (!input) return;
    input.classList.remove('pl-waveform-control-error');
    if (clearInvalid) input.classList.remove('pl-waveform-invalid');
    var badge = getTextInputParseErrorBadge(input);
    if (badge) badge.remove();
}

/** Mark a text input with the same parse-error badge used after submission. */
function showTextInputParseError(input, message) {
    if (!input) return;
    var container = input.closest('.pl-waveform');
    if (!container) return;

    clearTextInputParseError(input);
    input.classList.add('pl-waveform-control-error');

    var badge = createParseErrorBadge(getControlKey(input), message);
    positionParseErrorBadge(container, input, badge);
    container.appendChild(badge);
    showTimedTextInputHint(input, 1000);
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

    baseRows.forEach(function (baseRow) {
        var sigY = m.signalYMap[baseRow.signal_name];
        if (sigY === undefined) return;

        var rowY = getSignalRowBounds(m, baseRow.signal_name, sigY, 34);
        var rowElement = createToggleRowElement(container, baseRow, firstTickX, m.unitWidth, rowY);
        editorLayer.appendChild(rowElement);
    });
}

/** Create a toggle-mode row and its interactive cell buttons. */
function createToggleRowElement(container, rowModel, firstTickX, unitWidth, rowY) {
    var cellPeriod = rowModel.period || 1;
    var rowBounds = computeRowBoundsFromCells(rowModel.cells, firstTickX, unitWidth, cellPeriod) || {
        left: firstTickX,
        right: firstTickX + (rowModel.wave_length * unitWidth * cellPeriod)
    };
    var rowElement = document.createElement('div');
    rowElement.className = 'pl-waveform-editor-row';
    rowElement.setAttribute('data-signal', rowModel.signal_name);
    rowElement.setAttribute('data-allowed-values', JSON.stringify(rowModel.allowed_values || DEFAULT_ALLOWED_VALUES));
    if (rowModel.bus_width) rowElement.setAttribute('data-bus-width', rowModel.bus_width);
    rowElement.style.left = Math.round(rowBounds.left) + 'px';
    rowElement.style.top = Math.round(rowY.top) + 'px';
    rowElement.style.width = Math.round(rowBounds.right - rowBounds.left) + 'px';
    rowElement.style.height = Math.round(rowY.height) + 'px';

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
        if (rowModel.bus_width) hitTarget.setAttribute('data-bus-width', rowModel.bus_width);
        hitTarget.setAttribute('aria-label', cell.aria_label);
        hitTarget.style.left = Math.round(firstTickX + (cell.abs_index * unitWidth * cellPeriod) - rowBounds.left) + 'px';
        hitTarget.style.top = '0';
        hitTarget.style.width = Math.round(unitWidth * cellPeriod) + 'px';
        hitTarget.style.height = Math.round(rowY.height) + 'px';

        var hiddenInput = document.getElementById('pl-wf-hidden-' + cell.key);
        if (hiddenInput && hiddenInput.disabled) {
            hitTarget.disabled = true;
        }

        var initialValue = hiddenInput ? hiddenInput.value : cell.value;
        if (normalizeEditableValue(initialValue, rowModel.allowed_values || ['0', '1', 'x'], rowModel.bus_width) !== '') {
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

    baseRows.forEach(function (baseRow) {
        var sigY = m.signalYMap[baseRow.signal_name];
        if (sigY === undefined) return;
        var rowBounds = computeRowBoundsFromCells(baseRow.cells, tickSpan.left, m.unitWidth, baseRow.period) || tickSpan;
        var rowY = getSignalRowBounds(m, baseRow.signal_name, sigY, 34);

        var band = document.createElement('div');
        band.className = 'pl-waveform-editor-row';
        band.setAttribute('data-signal', baseRow.signal_name);
        band.style.left = Math.round(rowBounds.left) + 'px';
        band.style.top = Math.round(rowY.top) + 'px';
        band.style.width = Math.round(rowBounds.right - rowBounds.left) + 'px';
        band.style.height = Math.round(rowY.height) + 'px';
        editorLayer.appendChild(band);
    });
}



/** Advance a toggle cell to the next allowed state. */
function advanceRenderedCell(control) {
    var touched = control.getAttribute('data-touched') === 'true';
    var allowedValues = getAllowedValues(control);
    var states = touched ? allowedValues.slice() : [''].concat(allowedValues);
    var current = normalizeEditableValue(control.getAttribute('data-value'), allowedValues, getBusWidth(control));
    var idx = states.indexOf(current);
    if (idx === -1) idx = touched ? -1 : 0;
    setRenderedCellValue(control, states[(idx + 1) % states.length], { markTouched: true });
}


/** Update a toggle cell and synchronize the hidden input state. */
function setRenderedCellValue(control, value, options) {
    var opts = options || {};
    var allowedValues = getAllowedValues(control);
    var busWidth = getBusWidth(control);
    var container = control.closest('.pl-waveform');
    if (opts.markTouched) {
        control.setAttribute('data-touched', 'true');
    }

    var touched = control.getAttribute('data-touched') === 'true';
    var normalized = normalizeEditableValue(value, allowedValues, busWidth);
    if (touched && normalized === '') {
        var current = normalizeEditableValue(control.getAttribute('data-value'), allowedValues, busWidth);
        normalized = current || String(allowedValues[0] || '');
    }

    var hiddenInput = document.getElementById(control.getAttribute('data-hidden-input-id'));
    if (hiddenInput && !hiddenInput.disabled) {
        hiddenInput.value = normalized;
    }
    control.setAttribute('data-touched', touched ? 'true' : 'false');
    updateHitTargetMetadata(control, normalized);
    if (hasValidControlValue(control)) {
        clearTextInputParseError(control, true);
    }

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
        var contentW = getBusWidth(inp) ? (getBusWidth(inp) * 12 + 16) : 44;
        var inputW = Math.max(24, Math.min(Math.max(44, contentW), Math.round(slotWidth - 8)));
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
    if (!isMeasurableWaveform(container)) {
        deferUntilVisible(container);
        return;
    }

    container.removeAttribute('data-pl-waveform-pending-init');

    var panel = container.getAttribute('data-panel') || '';
    var inputMode = getInputMode(container);

    if (panel === 'question') {
        if (inputMode === 'toggle') {
            buildToggleEditor(container);
        } else {
            positionTextInputs(container);
            buildTextEditorRowBands(container);
        }
    }

    if (container.hasAttribute('data-cell-scores')) {
        renderScoreFeedback(container);
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
function appendCellOverlay(container, m, signalName, cycleNum, className, absIndex, period, text, title) {
    var sigY = m.signalYMap[signalName];
    var centreX = getSlotCenterX(m, absIndex, period, cycleNum);
    if (sigY === undefined || centreX === null) return;

    var overlay = document.createElement('div');
    overlay.className = 'pl-waveform-feedback-overlay pl-waveform-cell-feedback-overlay ' + className;
    if (title) {
        overlay.title = title;
        overlay.setAttribute('aria-label', title);
    }

    var overlayW = Math.max(18, m.unitWidth * getSlotPeriod(period, 1) * 0.85);
    var rowY = getSignalRowBounds(m, signalName, sigY, 28);

    overlay.style.left = Math.round(centreX - overlayW / 2) + 'px';
    overlay.style.top = Math.round(rowY.top) + 'px';
    overlay.style.width = Math.round(overlayW) + 'px';
    overlay.style.height = Math.round(rowY.height) + 'px';

    if (text) {
        var badge = document.createElement('span');
        badge.className = 'pl-waveform-cell-score-badge pl-waveform-cell-score-badge-corner ' +
            (className.indexOf('pl-waveform-feedback-correct') !== -1
                ? 'pl-waveform-cell-score-correct'
                : 'pl-waveform-cell-score-incorrect');
        badge.textContent = text;
        badge.setAttribute('aria-hidden', 'true');
        overlay.appendChild(badge);
    }

    container.appendChild(overlay);
}

/** Create the badge used for cell-level feedback. */
function createCellScoreBadge(cell, corner) {
    var badge = document.createElement(corner ? 'span' : 'div');
    var title = cell.correct
        ? 'correct'
        : (cell.invalid ? cell.invalid_message || 'invalid' : (cell.unanswered ? 'unanswered' : 'incorrect'));
    badge.className = 'pl-waveform-cell-score-badge ' +
        (corner ? 'pl-waveform-cell-score-badge-corner ' : '') +
        (cell.correct ? 'pl-waveform-cell-score-correct' : 'pl-waveform-cell-score-incorrect');
    badge.textContent = cell.correct ? '\u2713' : '\u2717';
    badge.title = title;
    if (corner) {
        badge.setAttribute('aria-hidden', 'true');
    } else {
        badge.setAttribute('aria-label', title);
    }
    return badge;
}

/** Return the CSS state class for one scored cell. */
function cellFeedbackClass(cell) {
    if (cell.correct) return 'pl-waveform-correct';
    if (cell.invalid) return 'pl-waveform-invalid';
    return cell.incorrect ? 'pl-waveform-incorrect' : 'pl-waveform-unanswered';
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

/** Create the exclamation badge used for parse errors. */
function createParseErrorBadge(key, message) {
    var badge = document.createElement('div');
    badge.className = 'pl-waveform-parse-error';
    badge.setAttribute('data-key', key);
    badge.textContent = '!';
    badge.title = message;
    badge.setAttribute('aria-label', message);
    return badge;
}

/** Return a parse-error message for an answer key. */
function parseErrorMessage(parseErrors, key) {
    var error = parseErrors[key];
    if (!error) return '';
    if (typeof error === 'string') return error;
    return error.message || '';
}

/** Position a parse-error badge over the top-right corner of a control. */
function positionParseErrorBadge(container, control, badge) {
    var badgeSize = 14;
    var containerRect = container.getBoundingClientRect();
    var controlRect = control.getBoundingClientRect();
    var relL = controlRect.left - containerRect.left;
    var relT = controlRect.top - containerRect.top;

    badge.style.left = Math.round(relL + controlRect.width - badgeSize / 2) + 'px';
    badge.style.top = Math.round(relT - badgeSize / 2) + 'px';
    badge.style.width = badgeSize + 'px';
    badge.style.height = badgeSize + 'px';
}

/** Return the vertical midpoint of editable signal rows. */
function editableSignalMidY(m, editableSignals, fallbackY) {
    var yVals = m
        ? editableSignals
            .map(function (signalName) { return m.signalYMap[signalName]; })
            .filter(function (y) { return y !== undefined; })
        : [];
    return yVals.length > 0
        ? yVals.reduce(function (a, b) { return a + b; }, 0) / yVals.length
        : fallbackY;
}

/** Return the right edge of the rendered waveform drawing. */
function waveformRightEdge(container) {
    var svg = container.querySelector('svg');
    var containerRect = container.getBoundingClientRect();
    if (!svg) return containerRect.width;
    try {
        var bbox = svg.getBBox();
        var right = toContainerPixels(svg, container, svg, bbox.x + bbox.width, bbox.y);
        if (right && Number.isFinite(right.x)) return right.x;
    } catch (e) { /* fall back to the SVG layout box */ }
    return svg.getBoundingClientRect().right - containerRect.left;
}

/** Position a whole-element badge immediately to the right of the drawing. */
function positionWholeElementBadge(container, badge, m, editableSignals, fallbackY) {
    var midY = editableSignalMidY(m, editableSignals, fallbackY);
    badge.style.left = Math.round(waveformRightEdge(container) + 8) + 'px';
    badge.style.top = Math.round(midY - 14) + 'px';
}

/** Add the element-level invalid-input warning beside a waveform. */
function appendParseErrorSummary(container, count, m, editableSignals) {
    var badge = document.createElement('div');
    badge.className = 'pl-waveform-parse-error-summary';
    badge.textContent = 'Input values were invalid';
    badge.title = count + ' invalid input value' + (count === 1 ? '' : 's');

    positionWholeElementBadge(container, badge, m, editableSignals, 18);
    container.appendChild(badge);
}

/** Add a read-only parse-error marker over a waveform cell. */
function appendParseErrorCellOverlay(container, m, cell, message) {
    var sigY = m.signalYMap[cell.signal_name];
    var centreX = getSlotCenterX(m, cell.abs_index, cell.period, cell.cycle_num);
    if (sigY === undefined || centreX === null) return;

    var overlayW = Math.max(18, m.unitWidth * getSlotPeriod(cell.period, 1) * 0.85);
    var rowY = getSignalRowBounds(m, cell.signal_name, sigY, 28);

    var overlay = document.createElement('div');
    overlay.className = 'pl-waveform-feedback-overlay pl-waveform-parse-error-cell-overlay';
    overlay.title = message;
    overlay.setAttribute('aria-label', message);
    overlay.style.left = Math.round(centreX - overlayW / 2) + 'px';
    overlay.style.top = Math.round(rowY.top) + 'px';
    overlay.style.width = Math.round(overlayW) + 'px';
    overlay.style.height = Math.round(rowY.height) + 'px';

    var badge = createParseErrorBadge(cell.key, message);
    badge.classList.add('pl-waveform-parse-error-corner');
    overlay.appendChild(badge);
    container.appendChild(overlay);
}

/** Render parse-error badges over invalid controls or read-only cells. */
function renderParseErrorOverlays(container) {
    var parseErrors = {};
    var parseErrorCells = [];
    try {
        parseErrors = JSON.parse(container.getAttribute('data-parse-errors') || '{}');
        parseErrorCells = JSON.parse(container.getAttribute('data-parse-error-cells') || '[]');
    } catch (e) { return; }

    getQuestionControls(container).forEach(function (control) {
        control.classList.remove('pl-waveform-control-error');
    });

    var errorKeys = Object.keys(parseErrors);
    if (errorKeys.length === 0) return;

    var displayedKeys = {};
    getQuestionControls(container).forEach(function (control) {
        var key = getControlKey(control);
        var message = parseErrorMessage(parseErrors, key);
        if (!message) return;

        control.classList.add('pl-waveform-control-error');
        var badge = createParseErrorBadge(key, message);
        positionParseErrorBadge(container, control, badge);

        container.appendChild(badge);
        displayedKeys[key] = true;
    });

    var editableSignals = getEditableSignals(container);
    var m = measureSVGPositions(container, editableSignals);

    parseErrorCells.forEach(function (cell) {
        if (displayedKeys[cell.key] || !m) return;
        var message = cell.message || parseErrorMessage(parseErrors, cell.key);
        if (!message) return;
        appendParseErrorCellOverlay(container, m, cell, message);
        displayedKeys[cell.key] = true;
    });

    appendParseErrorSummary(container, errorKeys.length, m, editableSignals);
}


// ═══════════════════════════════════════════════════════════════════════════
// Score feedback after submission
// ═══════════════════════════════════════════════════════════════════════════

/** Append one whole-element score badge to a waveform container. */
function appendElementScoreBadge(container, correct, total, pct, m, editableSignals) {
    var badge = document.createElement('div');
    badge.className = 'pl-waveform-element-score-badge';
    if (pct === 100) badge.classList.add('pl-waveform-element-score-correct');
    else badge.classList.add('pl-waveform-element-score-incorrect');

    badge.textContent = correct + ' out of ' + total;
    badge.title = pct + '% correct';

    positionWholeElementBadge(container, badge, m, editableSignals, 40);
    container.appendChild(badge);
}

/** Render score overlays for the configured feedback mode. */
function renderScoreFeedback(container) {
    var editableSignals = getEditableSignals(container);
    var feedback = container.getAttribute('data-feedback') || 'cell';
    var inputMode = getInputMode(container);
    var cellScores = [];

    try {
        cellScores = JSON.parse(container.getAttribute('data-cell-scores') || '[]');
    } catch (e) { return; }

    if (cellScores.length === 0) return;
    clearScoreFeedbackState(container);

    if (feedback === 'cell') {
        var toggleControls = Array.from(container.querySelectorAll('.pl-waveform-cell-hit'));
        if (inputMode === 'toggle' && toggleControls.length > 0) {
            var toggleScoreMap = {};
            cellScores.forEach(function (cell) {
                toggleScoreMap[cell.signal_name + '|' + cell.cycle_num] = cell;
            });

            toggleControls.forEach(function (control) {
                var mapKey = control.getAttribute('data-signal') + '|' + control.getAttribute('data-cycle');
                var cell = toggleScoreMap[mapKey];
                if (!cell) return;

                clearFeedbackClasses(control);
                control.classList.add(cellFeedbackClass(cell));

                control.appendChild(createCellScoreBadge(cell, true));
            });
            return;
        }

        var textControls = Array.from(container.querySelectorAll('.pl-waveform-proxy'));
        if (inputMode === 'text' && textControls.length > 0) {
            // Text-mode keeps direct input tinting plus a small status badge.
            var BADGE = 14;
            var containerRect = container.getBoundingClientRect();
            var scoreMap = {};
            cellScores.forEach(function (cell) {
                scoreMap[cell.signal_name + '|' + cell.cycle_num] = cell;
            });

            textControls.forEach(function (inp) {
                var mapKey = inp.getAttribute('data-signal') + '|' + inp.getAttribute('data-cycle');
                var cell = scoreMap[mapKey];
                clearFeedbackClasses(inp);
                if (!cell) return;
                inp.classList.add(cellFeedbackClass(cell));

                var r = inp.getBoundingClientRect();
                var relL = r.left - containerRect.left;
                var relT = r.top - containerRect.top;

                var badge = createCellScoreBadge(cell, false);
                badge.style.left = Math.round(relL + r.width - BADGE / 2) + 'px';
                badge.style.top = Math.round(relT - BADGE / 2) + 'px';
                badge.style.width = BADGE + 'px';
                badge.style.height = BADGE + 'px';
                container.appendChild(badge);
            });
            return;
        }

        var mCell = measureSVGPositions(container, editableSignals);
        if (!mCell) return;
        cellScores.forEach(function (cell) {
            if (cell.correct) {
                appendCellOverlay(
                    container,
                    mCell,
                    cell.signal_name,
                    cell.cycle_num,
                    'pl-waveform-feedback-correct',
                    cell.abs_index,
                    cell.period,
                    '\u2713',
                    'correct'
                );
            } else {
                appendCellOverlay(
                    container,
                    mCell,
                    cell.signal_name,
                    cell.cycle_num,
                    'pl-waveform-feedback-incorrect',
                    cell.abs_index,
                    cell.period,
                    '\u2717',
                    cell.invalid ? (cell.invalid_message || 'invalid') : (cell.unanswered ? 'unanswered' : 'incorrect')
                );
            }
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
            pill.style.top = Math.round(sigY - 10) + 'px';
            container.appendChild(pill);
        });
        return;
    }

    if (feedback === 'element') {
        var mElement = measureSVGPositions(container, editableSignals);
        if (!mElement || mElement.sortedTicks.length === 0) return;

        var total = cellScores.length;
        var correct = cellScores.filter(function (cell) { return cell.correct; }).length;
        var pct = total > 0 ? Math.round(100 * correct / total) : 0;
        appendElementScoreBadge(container, correct, total, pct, mElement, editableSignals);
    }
}
