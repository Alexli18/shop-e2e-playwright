// Vanilla-JS stand-ins for the shop's jQuery scripts (public.common.js, public.ajaxcart.js),
// keeping the DOM effects the page objects rely on.

// public.common.js: displayBarNotification -- one <p class="content"> per message, then a fade-in.
function displayBarNotification(message, messagetype) {
  var bar = document.getElementById('bar-notification');
  bar.classList.remove('success', 'error');
  bar.querySelectorAll('.content').forEach(function (e) { e.remove(); });
  var messages = (typeof message === 'string') ? [message] : message;
  messages.forEach(function (text) {
    var p = document.createElement('p');
    p.className = 'content';
    p.innerHTML = text;
    bar.appendChild(p);
  });
  bar.classList.add(messagetype === 'error' ? 'error' : 'success');
  bar.style.opacity = '0';
  bar.style.display = 'block';
  requestAnimationFrame(function () { requestAnimationFrame(function () { bar.style.opacity = '1'; }); });
}

// public.ajaxcart.js: POST the product form, update the header counter, show the bar.
var AjaxCart = {
  addproducttocart_details: function (url, formselector) {
    var loading = document.querySelector('.ajax-loading-block-window');
    loading.style.display = 'block';
    var body = new URLSearchParams(new FormData(document.querySelector(formselector)));
    fetch(url, { method: 'POST', body: body })
      .then(function (r) { return r.json(); })
      .then(function (response) {
        if (response.updatetopcartsectionhtml) {
          document.querySelector('.header-links .cart-qty').innerHTML = response.updatetopcartsectionhtml;
        }
        loading.style.display = 'none';
        displayBarNotification(response.message, response.success ? 'success' : 'error');
      });
  }
};

document.addEventListener('DOMContentLoaded', function () {
  // Search page: the 'Advanced search' checkbox shows/hides the price range block.
  var advanced = document.getElementById('As');
  var block = document.getElementById('advanced-search-block');
  if (advanced && block) {
    var toggle = function () { block.style.display = advanced.checked ? 'block' : 'none'; };
    advanced.addEventListener('click', toggle);
    toggle();
  }
  var close = document.querySelector('#bar-notification .close');
  close.addEventListener('click', function () { document.getElementById('bar-notification').style.display = 'none'; });
});
