$(document).ready(function() {
    // Format table to provide sort feature
    $('#balance-table').DataTable({
        paging: false,
        searching: false,
        "info": false,
        "order": [
            [3, "desc"]
        ]
    });
    $('.dataTables_wrapper').find('label').each(function() {
        $(this).parent().append($(this).children());
    });
    $('.dataTables_filter').find('input').each(function() {
        $('input').attr("placeholder", "Search");
        $('input').removeClass('form-control-sm');
    });
    $('.dataTables_length').addClass('d-flex flex-row');
    $('.dataTables_filter').addClass('md-form');
    $('select').addClass('mdb-select');
    // $('.mdb-select').material_select();
    $('.mdb-select').removeClass('form-control form-control-sm');
    $('.dataTables_filter').find('label').remove();

    // Format table contents
    $('#balance-table .color-sign').each(function(i, cell) {
        content = $(this).text();
        if (content.length > 2) {
            num = parseFloat(content.substr(0, content.length - 2));
            if (num < 0) {
                $(this).css({
                    color: 'red'
                });
            } else if (num > 0) {
                $(this).css({
                    color: 'green'
                });
            } else {
                $(this).html('-')
            }

        }
    });


});