(function($) {
  'use strict';

  var $navToggle = $('#navToggle');
  var $navLinks = $('#navLinks');

  $navToggle.on('click', function() {
    $(this).toggleClass('active');
    $navLinks.toggleClass('active');
  });

  $navLinks.find('a').on('click', function() {
    $navToggle.removeClass('active');
    $navLinks.removeClass('active');
  });

  if ($.fancybox) {
    $('.post-content img').each(function() {
      if ($(this).parent().hasClass('fancybox') || $(this).parent().is('a')) return;
      $(this).wrap('<a href="' + this.src + '" data-fancybox="gallery" data-caption="' + (this.alt || '') + '"></a>');
    });
    $('.fancybox').fancybox();
  }

})(jQuery);

// --- Career page: toggle detail ---
$('.career-toggle-btn').on('click', function(e) {
  e.preventDefault();
  var $btn = $(this);
  var $detail = $btn.closest('.career-card-body').find('.career-detail');
  $detail.slideToggle(300);
  $btn.toggleClass('active');
  $btn.find('span').text($btn.hasClass('active') ? 'Show less' : 'Read more');
});

// --- Career page: timeline dot scroll ---
$('.timeline-dot').on('click', function() {
  var target = $(this).data('target');
  var $target = $('#' + target);
  if ($target.length) {
    $('html, body').animate({
      scrollTop: $target.offset().top - 100
    }, 400);
  }
});
