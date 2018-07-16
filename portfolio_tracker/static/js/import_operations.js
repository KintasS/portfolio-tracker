$(document).ready(function() {

    $('.modal-footer input').on('click', function() {
        $(this).fadeOut();
        $('.modal-header button').fadeOut();
    });

});