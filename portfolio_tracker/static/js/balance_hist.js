$(document).ready(function() {

    $('#datepicker').datepicker({
        showOtherMonths: true,
        format: 'yyyy-mm-dd'
    });

    $(".date").datepicker({
        onSelect: function() {
            $(this).change();
        }
    });

    var href = '/balance/';

    $('#datepicker').on('change', function() {
        // alert("llego");
        var newudate = $('#datepicker').val();
        $('#submit-btn').attr('href', href + newudate);
    });


});