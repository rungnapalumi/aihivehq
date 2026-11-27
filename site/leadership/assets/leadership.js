/* AIHive Leadership — shared page behaviour (nav, reveal, mission cards). */
(function () {
  'use strict';
  var burger = document.querySelector('.l-burger');
  var mobile = document.getElementById('l-mobile');
  if (burger && mobile) {
    burger.addEventListener('click', function () {
      var open = mobile.classList.toggle('open');
      burger.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    mobile.querySelectorAll('a').forEach(function (a) { a.addEventListener('click', function () { mobile.classList.remove('open'); burger.setAttribute('aria-expanded', 'false'); }); });
  }
  var els = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
    }, { threshold: 0.12 });
    els.forEach(function (el) { io.observe(el); });
  } else { els.forEach(function (el) { el.classList.add('in'); }); }
  document.querySelectorAll('.mission').forEach(function (card) {
    card.addEventListener('click', function () {
      var open = card.getAttribute('aria-expanded') === 'true';
      card.setAttribute('aria-expanded', open ? 'false' : 'true');
      var t = card.querySelector('.toggle'); if (t) t.textContent = open ? 'Show details' : 'Hide details';
    });
  });
}());
