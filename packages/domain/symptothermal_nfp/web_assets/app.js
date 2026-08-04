const state = {
  data: null,
  activeView: 'today',
  selectedDate: null,
  selectedCycleIndex: 0,
  editorUnit: 'fahrenheit',
  toastTimer: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

document.addEventListener('DOMContentLoaded', () => {
  bindEvents();
  void loadBootstrap();
});

function bindEvents() {
  $$('.nav-item').forEach((button) => {
    button.addEventListener('click', () => selectView(button.dataset.view));
  });

  $('#active-date').addEventListener('change', (event) => {
    state.selectedDate = event.target.value;
    renderToday();
  });

  $$('.save-section').forEach((button) => {
    button.addEventListener('click', () => void saveObservation(button.dataset.save));
  });

  $('#open-settings').addEventListener('click', openSettings);
  $('#close-settings').addEventListener('click', closeSettings);
  $('#cancel-settings').addEventListener('click', closeSettings);
  $('#settings-form').addEventListener('submit', (event) => {
    event.preventDefault();
    void saveChartSettings();
  });

  $('#cycle-select').addEventListener('change', (event) => {
    state.selectedCycleIndex = Number(event.target.value);
    renderChart();
  });

  document.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
      event.preventDefault();
      if (state.activeView === 'today') void saveObservation('entry');
    }
  });
}

async function loadBootstrap() {
  try {
    state.data = await api('/api/bootstrap');
    state.selectedDate = state.data.today;
    state.selectedCycleIndex = Math.max(state.data.report.cycles.length - 1, 0);
    $('#loading').hidden = true;
    $('#view-today').hidden = false;
    renderAll();
    if (!state.data.settings.setup_complete) openSettings();
  } catch (error) {
    $('#loading').textContent = `Unable to open chart: ${error.message}`;
    showToast(error.message, true);
  }
}

function renderAll() {
  $('#active-date').value = state.selectedDate;
  renderToday();
  renderCycleOptions();
  renderChart();
  renderHistory();
  fillSettingsForm();
}

function selectView(view) {
  state.activeView = view;
  const titles = { today: 'Today', chart: 'Cycle chart', history: 'Cycle history' };
  $('#page-title').textContent = titles[view];
  $$('.view').forEach((section) => { section.hidden = section.id !== `view-${view}`; });
  $$('.nav-item').forEach((button) => {
    const active = button.dataset.view === view;
    button.classList.toggle('is-active', active);
    if (active) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  });
  if (view === 'chart') renderChart();
}

function renderToday() {
  if (!state.data || !state.selectedDate) return;
  const observation = observationForDate(state.selectedDate);
  const interpretation = interpretationForDate(state.selectedDate);
  state.editorUnit = observation.temperature_unit || state.data.settings.temperature_unit;

  $('#selected-date-label').textContent = formatLongDate(state.selectedDate).toUpperCase();
  $('#active-date').value = state.selectedDate;
  $('#cycle-day-label').textContent = interpretation ? `Cycle day ${interpretation.cycle_day}` : 'New chart entry';
  $('#temperature').value = observation.waking_temperature ?? '';
  $('#temperature').placeholder = state.editorUnit === 'fahrenheit' ? '97.60' : '36.45';
  $('#temperature-unit-label').textContent = state.editorUnit === 'fahrenheit' ? '°F' : '°C';
  $('#temperature-time').value = observation.temperature_time || state.data.settings.default_wake_time;
  $('#notes').value = observation.notes || '';

  $$('#disturbance-options input').forEach((input) => {
    input.checked = observation.temperature_disturbances.includes(input.value);
  });
  setRadio('mucus', observation.mucus_sign || 'not_checked');
  setRadio('bleeding', observation.bleeding || 'none');
  renderFeedback(interpretation);
}

function observationForDate(date) {
  const existing = state.data.observations.find((item) => item.date === date);
  if (existing) return existing;
  if (date === state.data.today) return state.data.today_observation;
  return {
    date,
    waking_temperature: null,
    temperature_unit: state.data.settings.temperature_unit,
    temperature_time: state.data.settings.default_wake_time,
    temperature_disturbances: [],
    mucus_sign: 'not_checked',
    bleeding: 'none',
    notes: '',
  };
}

function interpretationForDate(date) {
  if (date === state.data.today) return state.data.today_interpretation;
  for (const cycle of state.data.report.cycles) {
    const day = cycle.days.find((item) => item.observation_date === date);
    if (day) return day;
  }
  return null;
}

function renderFeedback(interpretation) {
  const fallback = {
    feedback: {
      label: 'not_enough_information',
      headline: 'Not enough information',
      summary: 'No temperature or mucus observation is available for this day.',
      action: 'Record temperature and the most fertile mucus sign noticed.',
    },
    progress: {
      temperature_high_count: 0,
      temperature_high_required: 4,
      temperature_confirmed: false,
      mucus_lower_quality_count: 0,
      mucus_lower_quality_required: 3,
      mucus_confirmed: false,
      next_step: 'Record a waking temperature before getting out of bed.',
      data_quality_messages: [],
    },
  };
  const value = interpretation || fallback;
  const feedback = value.feedback || fallback.feedback;
  const progress = value.progress || fallback.progress;
  const card = $('#feedback-card');
  card.classList.remove('is-possible', 'is-confirmed', 'is-lower', 'is-incomplete');
  const classByLabel = {
    fertility_possible: 'is-possible',
    post_ovulation_confirmed: 'is-confirmed',
    lower_probability_method_rules_apply: 'is-lower',
    not_enough_information: 'is-incomplete',
  };
  card.classList.add(classByLabel[feedback.label] || 'is-incomplete');
  $('#feedback-headline').textContent = feedback.headline;
  $('#feedback-summary').textContent = feedback.summary;
  $('#feedback-action').textContent = feedback.action;

  const tempLabel = progress.temperature_confirmed
    ? 'Confirmed'
    : `${progress.temperature_high_count} / ${progress.temperature_high_required} elevated`;
  const mucusLabel = progress.mucus_confirmed
    ? 'Confirmed'
    : `${progress.mucus_lower_quality_count} / ${progress.mucus_lower_quality_required} after Peak`;
  $('#temperature-progress-label').textContent = tempLabel;
  $('#mucus-progress-label').textContent = mucusLabel;
  $('#temperature-progress-bar').style.width = progress.temperature_confirmed
    ? '100%'
    : `${percentage(progress.temperature_high_count, progress.temperature_high_required)}%`;
  $('#mucus-progress-bar').style.width = progress.mucus_confirmed
    ? '100%'
    : `${percentage(progress.mucus_lower_quality_count, progress.mucus_lower_quality_required)}%`;
  $('#next-step-text').textContent = progress.next_step;
  const qualityList = $('#quality-messages');
  qualityList.replaceChildren(...(progress.data_quality_messages || []).map((message) => element('li', message)));
  qualityList.hidden = !qualityList.children.length;
  $('#rule-version').textContent = state.data.report.rule_pack_version;
}

async function saveObservation(section) {
  const temperatureText = $('#temperature').value.trim();
  const temperature = temperatureText === '' ? null : Number(temperatureText);
  const minimum = state.editorUnit === 'fahrenheit' ? 80 : 30;
  const maximum = state.editorUnit === 'fahrenheit' ? 110 : 45;
  if (temperature !== null && (!Number.isFinite(temperature) || temperature < minimum || temperature > maximum)) {
    showToast(`Enter a realistic ${state.editorUnit === 'fahrenheit' ? 'Fahrenheit' : 'Celsius'} body temperature.`, true);
    $('#temperature').focus();
    return;
  }

  const disturbances = $$('#disturbance-options input:checked').map((input) => input.value);
  if (temperature === null && disturbances.length) {
    showToast('Enter a temperature before adding disturbance flags.', true);
    return;
  }

  const payload = {
    waking_temperature: temperature,
    temperature_unit: state.editorUnit,
    temperature_time: $('#temperature-time').value || null,
    temperature_disturbances: disturbances,
    mucus_sign: checkedValue('mucus', 'not_checked'),
    bleeding: checkedValue('bleeding', 'none'),
    notes: $('#notes').value,
  };
  const buttons = $$('.save-section');
  buttons.forEach((button) => { button.disabled = true; });
  try {
    state.data = await api(`/api/observations/${encodeURIComponent(state.selectedDate)}`, {
      method: 'PUT',
      body: payload,
    });
    state.selectedCycleIndex = Math.max(state.data.report.cycles.length - 1, 0);
    renderAll();
    const labels = { morning: 'Morning temperature saved.', evening: 'Evening signs saved.', entry: 'Daily entry saved.' };
    showToast(labels[section] || 'Entry saved.');
  } catch (error) {
    showToast(error.message, true);
  } finally {
    buttons.forEach((button) => { button.disabled = false; });
  }
}

function renderCycleOptions() {
  const select = $('#cycle-select');
  const cycles = state.data.report.cycles;
  select.replaceChildren(...cycles.map((cycle, index) => {
    const option = document.createElement('option');
    option.value = String(index);
    option.textContent = `Cycle ${cycle.cycle_index} · ${formatShortDate(cycle.start_date)}`;
    return option;
  }));
  if (cycles.length) {
    state.selectedCycleIndex = Math.min(state.selectedCycleIndex, cycles.length - 1);
    select.value = String(state.selectedCycleIndex);
  }
}

function renderChart() {
  if (!state.data) return;
  const cycles = state.data.report.cycles;
  const cycle = cycles[state.selectedCycleIndex];
  $('#chart-empty').hidden = Boolean(cycle);
  $('#chart-content').hidden = !cycle;
  if (!cycle) return;

  $('#cycle-select').value = String(state.selectedCycleIndex);
  $('#chart-range').textContent = `${formatShortDate(cycle.start_date)} – ${formatShortDate(cycle.end_date)}`;
  $('#chart-peak').textContent = cycle.peak_day ? formatShortDate(cycle.peak_day) : 'Not confirmed';
  $('#chart-temperature').textContent = cycle.temperature_shift
    ? formatShortDate(cycle.temperature_shift.confirmed_date)
    : 'Not confirmed';
  $('#chart-post').textContent = cycle.absolute_infertility_start_date
    ? `${formatShortDate(cycle.absolute_infertility_start_date)} evening`
    : 'Not confirmed';

  drawCycleChart(cycle);
  const warnings = cycle.warnings || [];
  $('#chart-warnings').hidden = !warnings.length;
  $('#chart-warnings ul').replaceChildren(...warnings.map((warning) => element('li', warning.message)));
}

function drawCycleChart(cycle) {
  const root = $('#chart-root');
  const observations = cycle.days.map((day) => {
    const observation = state.data.observations.find((item) => item.date === day.observation_date);
    return { day, observation };
  });
  const width = Math.max(960, observations.length * 58 + 100);
  const height = 390;
  const left = 64;
  const right = 28;
  const top = 34;
  const plotBottom = 260;
  const plotHeight = plotBottom - top;
  const dayWidth = (width - left - right) / Math.max(observations.length, 1);
  const temperatures = observations
    .filter(({ observation }) => observation && observation.waking_temperature !== null && !observation.temperature_disturbances.length)
    .map(({ observation }) => normalizeTemperature(observation));
  const defaultRange = state.data.settings.temperature_unit === 'fahrenheit' ? [96.8, 99.2] : [36, 37.4];
  const minTemperature = temperatures.length ? Math.floor((Math.min(...temperatures) - .15) * 10) / 10 : defaultRange[0];
  const maxTemperature = temperatures.length ? Math.ceil((Math.max(...temperatures) + .15) * 10) / 10 : defaultRange[1];
  const yFor = (value) => top + ((maxTemperature - value) / Math.max(maxTemperature - minTemperature, .1)) * plotHeight;
  const xFor = (index) => left + dayWidth * index + dayWidth / 2;

  const svg = svgElement('svg', {
    width,
    height,
    viewBox: `0 0 ${width} ${height}`,
    role: 'img',
    'aria-label': `Cycle ${cycle.cycle_index} temperature and symptom chart`,
  });
  svg.appendChild(svgElement('title', {}, `Cycle ${cycle.cycle_index} temperature and symptom chart`));

  observations.forEach(({ day }, index) => {
    const label = day.feedback?.label || 'not_enough_information';
    const colors = {
      fertility_possible: '#fff0c7',
      post_ovulation_confirmed: '#ddf3e4',
      lower_probability_method_rules_apply: '#ddebf7',
      not_enough_information: '#e8eaed',
    };
    svg.appendChild(svgElement('rect', {
      x: left + dayWidth * index,
      y: top,
      width: dayWidth,
      height: height - top - 28,
      fill: colors[label] || colors.not_enough_information,
      opacity: .67,
    }));
  });

  for (let tick = 0; tick <= 5; tick += 1) {
    const value = minTemperature + ((maxTemperature - minTemperature) * tick) / 5;
    const y = yFor(value);
    svg.appendChild(svgElement('line', { x1: left, y1: y, x2: width - right, y2: y, stroke: '#d6dfdc', 'stroke-width': 1 }));
    svg.appendChild(svgText(8, y + 4, value.toFixed(1), { fill: '#6d7f7f', 'font-size': 10 }));
  }

  let previousPoint = null;
  observations.forEach(({ observation }, index) => {
    if (!observation || observation.waking_temperature === null || observation.temperature_disturbances.length) {
      previousPoint = null;
      return;
    }
    const point = { x: xFor(index), y: yFor(normalizeTemperature(observation)) };
    if (previousPoint) {
      svg.appendChild(svgElement('line', { x1: previousPoint.x, y1: previousPoint.y, x2: point.x, y2: point.y, stroke: '#1f6464', 'stroke-width': 2.2 }));
    }
    svg.appendChild(svgElement('circle', { cx: point.x, cy: point.y, r: 4.5, fill: '#1f6464', stroke: '#fff', 'stroke-width': 2 }));
    previousPoint = point;
  });

  if (cycle.temperature_shift) {
    let coverline = cycle.temperature_shift.coverline_celsius;
    if (state.data.settings.temperature_unit === 'fahrenheit') coverline = coverline * 9 / 5 + 32;
    const y = yFor(coverline);
    svg.appendChild(svgElement('line', { x1: left, y1: y, x2: width - right, y2: y, stroke: '#9e4537', 'stroke-width': 1.5, 'stroke-dasharray': '6 5' }));
    svg.appendChild(svgText(width - right - 4, y - 6, `Coverline ${coverline.toFixed(2)}`, { fill: '#9e4537', 'font-size': 9, 'text-anchor': 'end' }));
  }

  svg.appendChild(svgText(8, 18, `Temperature (°${state.data.settings.temperature_unit === 'fahrenheit' ? 'F' : 'C'})`, { fill: '#34575a', 'font-size': 10, 'font-weight': 700 }));
  svg.appendChild(svgText(8, 302, 'Mucus', { fill: '#6d7f7f', 'font-size': 10, 'font-weight': 700 }));
  svg.appendChild(svgText(8, 334, 'Bleeding', { fill: '#6d7f7f', 'font-size': 10, 'font-weight': 700 }));

  observations.forEach(({ day, observation }, index) => {
    const x = xFor(index);
    svg.appendChild(svgText(x, 281, String(day.cycle_day), { fill: '#173c40', 'font-size': 9, 'font-weight': 800, 'text-anchor': 'middle' }));
    svg.appendChild(svgText(x, 303, mucusAbbreviation(observation?.mucus_sign), { fill: '#694c7b', 'font-size': 10, 'font-weight': 800, 'text-anchor': 'middle' }));
    svg.appendChild(svgText(x, 335, bleedingAbbreviation(observation?.bleeding), { fill: '#9e4537', 'font-size': 10, 'font-weight': 800, 'text-anchor': 'middle' }));
  });
  svg.appendChild(svgText((left + width - right) / 2, 372, 'Cycle day', { fill: '#6d7f7f', 'font-size': 10, 'text-anchor': 'middle' }));
  root.replaceChildren(svg);
}

function renderHistory() {
  if (!state.data) return;
  const cycles = [...state.data.report.cycles].reverse();
  $('#history-empty').hidden = cycles.length > 0;
  $('#history-body').replaceChildren(...cycles.map((cycle) => {
    const latest = cycle.days.at(-1);
    const row = document.createElement('tr');
    row.append(
      tableCell(`Cycle ${cycle.cycle_index}`, true),
      tableCell(`${formatShortDate(cycle.start_date)} – ${formatShortDate(cycle.end_date)}`),
      tableCell(`${cycle.span_days} days`),
      tableCell(`${cycle.logged_days} days`),
      tableCell(latest?.feedback?.headline || 'Not enough information'),
    );
    const actionCell = document.createElement('td');
    const button = element('button', 'View chart');
    button.type = 'button';
    button.className = 'table-action';
    button.addEventListener('click', () => {
      state.selectedCycleIndex = state.data.report.cycles.indexOf(cycle);
      renderCycleOptions();
      selectView('chart');
    });
    actionCell.appendChild(button);
    row.appendChild(actionCell);
    return row;
  }));
}

function openSettings() {
  fillSettingsForm();
  const firstSetup = !state.data.settings.setup_complete;
  $('#close-settings').hidden = firstSetup;
  $('#cancel-settings').hidden = firstSetup;
  $('#settings-dialog').showModal();
}

function closeSettings() {
  if (!state.data.settings.setup_complete) return;
  $('#settings-dialog').close();
}

function fillSettingsForm() {
  if (!state.data) return;
  setRadio('tracking-goal', state.data.settings.tracking_goal);
  setRadio('temperature-unit', state.data.settings.temperature_unit);
  $('#default-wake-time').value = state.data.settings.default_wake_time;
  $('#rule-context').value = state.data.settings.rule_context;
}

async function saveChartSettings() {
  const payload = {
    ...state.data.settings,
    tracking_goal: checkedValue('tracking-goal', 'understand_cycle'),
    temperature_unit: checkedValue('temperature-unit', 'fahrenheit'),
    default_wake_time: $('#default-wake-time').value,
    rule_context: $('#rule-context').value,
    setup_complete: true,
  };
  try {
    state.data = await api('/api/settings', { method: 'PUT', body: payload });
    state.editorUnit = state.data.settings.temperature_unit;
    $('#settings-dialog').close();
    renderAll();
    showToast('Chart setup saved.');
  } catch (error) {
    showToast(error.message, true);
  }
}

async function api(path, options = {}) {
  const request = { method: options.method || 'GET', headers: {} };
  if (options.body !== undefined) {
    request.headers['Content-Type'] = 'application/json';
    request.headers['X-Symptothermal-Client'] = 'desktop-web';
    request.body = JSON.stringify(options.body);
  }
  const response = await fetch(path, request);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status}).`);
  return payload;
}

function normalizeTemperature(observation) {
  const value = Number(observation.waking_temperature);
  const target = state.data.settings.temperature_unit;
  if (observation.temperature_unit === target) return value;
  if (observation.temperature_unit === 'celsius') return value * 9 / 5 + 32;
  return (value - 32) * 5 / 9;
}

function checkedValue(name, fallback) {
  return document.querySelector(`input[name="${name}"]:checked`)?.value || fallback;
}

function setRadio(name, value) {
  const input = document.querySelector(`input[name="${name}"][value="${value}"]`);
  if (input) input.checked = true;
}

function percentage(value, total) {
  return total ? Math.max(0, Math.min(100, (value / total) * 100)) : 0;
}

function formatLongDate(value) {
  return new Intl.DateTimeFormat(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
    .format(new Date(`${value}T12:00:00`));
}

function formatShortDate(value) {
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
    .format(new Date(`${value}T12:00:00`));
}

function mucusAbbreviation(value) {
  return ({ not_checked: '—', dry: 'D', sticky: 'S', creamy: 'C', wet: 'W', slippery: 'Sl' })[value] || '—';
}

function bleedingAbbreviation(value) {
  return ({ none: '', spotting: 'Sp', light: 'L', medium: 'M', heavy: 'H' })[value] || '';
}

function element(tag, text) {
  const node = document.createElement(tag);
  node.textContent = text;
  return node;
}

function tableCell(text, strong = false) {
  const cell = document.createElement('td');
  const content = strong ? document.createElement('strong') : document.createTextNode(text);
  if (strong) content.textContent = text;
  cell.appendChild(content);
  return cell;
}

function svgElement(name, attributes) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', name);
  Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
  return node;
}

function svgText(x, y, text, attributes = {}) {
  const node = svgElement('text', { x, y, ...attributes });
  node.textContent = text;
  return node;
}

function showToast(message, isError = false) {
  const toast = $('#toast');
  toast.textContent = message;
  toast.classList.toggle('is-error', isError);
  toast.hidden = false;
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => { toast.hidden = true; }, 3200);
}
