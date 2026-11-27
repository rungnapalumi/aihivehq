/* AIHive Leadership — corporate inquiry form.
 * Client-side checks mirror the server rules in leadership/inquiry.py (the server is authoritative).
 * The endpoint comes from the form's data-endpoint attribute. No secrets live in this file. */
(function () {
  'use strict';
  var form = document.getElementById('inquiry-form');
  if (!form) return;
  var ok = document.getElementById('f-ok');
  var err = document.getElementById('f-err');
  var btn = document.getElementById('f-submit');
  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
  var PHONE_RE = /^[0-9+()\-.\s]{6,40}$/;

  function today() { var d = new Date(); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); }
  var dateInput = form.querySelector('[name="preferred_date"]');
  if (dateInput) dateInput.min = today();

  function setInvalid(name, bad) {
    var el = form.querySelector('[name="' + name + '"]');
    if (!el) return;
    var f = el.closest('.field');
    if (f) f.classList.toggle('invalid', !!bad);
    el.setAttribute('aria-invalid', bad ? 'true' : 'false');
  }

  function collect() {
    var data = {};
    ['full_name', 'company', 'email', 'phone', 'participants', 'duration', 'objectives', 'preferred_date', 'additional', 'website'].forEach(function (k) {
      var el = form.querySelector('[name="' + k + '"]'); data[k] = el ? el.value.trim() : '';
    });
    data.consent = form.querySelector('[name="consent"]').checked;
    return data;
  }

  function validate(d) {
    var errors = {};
    if (d.full_name.length < 2) errors.full_name = 1;
    if (d.company.length < 2) errors.company = 1;
    if (!EMAIL_RE.test(d.email)) errors.email = 1;
    if (d.phone && !PHONE_RE.test(d.phone)) errors.phone = 1;
    if (!d.participants) errors.participants = 1;
    if (!d.duration) errors.duration = 1;
    if (d.objectives.length < 10) errors.objectives = 1;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(d.preferred_date) || d.preferred_date < today()) errors.preferred_date = 1;
    if (!d.consent) errors.consent = 1;
    return errors;
  }

  function show(el, html) { ok.classList.remove('show'); err.classList.remove('show'); el.innerHTML = html; el.classList.add('show'); el.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }

  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    ok.classList.remove('show'); err.classList.remove('show');
    var d = collect();
    var errors = validate(d);
    ['full_name', 'company', 'email', 'phone', 'participants', 'duration', 'objectives', 'preferred_date', 'consent'].forEach(function (k) { setInvalid(k, errors[k]); });
    if (Object.keys(errors).length) {
      show(err, '<strong>Please check the highlighted fields.</strong>');
      var first = form.querySelector('[aria-invalid="true"]'); if (first) first.focus();
      return;
    }
    btn.disabled = true; btn.textContent = 'Sending…';
    fetch(form.getAttribute('data-endpoint'), {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' }, body: JSON.stringify(d)
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (body) { return { status: res.status, body: body }; });
    }).then(function (r) {
      if (r.status === 201 && r.body.ok) {
        form.querySelectorAll('input:not([type=checkbox]),select,textarea').forEach(function (el) { el.value = ''; });
        form.querySelector('[name="consent"]').checked = false;
        var msg = '<strong>Thank you — your inquiry has been received.</strong> Reference: <code>' + String(r.body.reference).replace(/[^A-Z0-9-]/g, '') + '</code>.<br>';
        msg += r.body.email_delivery === 'sent'
          ? 'A notification has been sent to the AIHiveHQ team.'
          : 'Your request is stored securely for the AIHiveHQ team to review. (Automatic email notification is not enabled in this test environment yet.)';
        show(ok, msg);
      } else if (r.status === 400 && r.body.errors) {
        Object.keys(r.body.errors).forEach(function (k) { setInvalid(k, true); });
        show(err, '<strong>Please check the highlighted fields.</strong>');
      } else if (r.status === 429) {
        show(err, '<strong>Too many requests.</strong> Please wait a few minutes and try again.');
      } else { throw new Error('status ' + r.status); }
    }).catch(function () {
      show(err, '<strong>Sorry, we could not send your inquiry right now.</strong> Please try again later or email <a href="mailto:rungnapa@aihivehq.com">rungnapa@aihivehq.com</a>.');
    }).then(function () { btn.disabled = false; btn.textContent = 'Send inquiry'; });
  });
}());
