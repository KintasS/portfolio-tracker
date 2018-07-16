$(document).ready(function() {

    $('.carousel').carousel({
        interval: 30000
    })

    function divide(num, den) {
        if (den == 0) {
            return '-';
        } else {
            return ((num / den * 100).toFixed(2) + ' %');
        }
    }

    // Format tables to provide sort feature
    $('.js-table').each(function(i, cell) {
        $(this).find('.table').DataTable({
            paging: false,
            searching: false,
            "info": false,
            "order": [
                [2, "desc"]
            ]
        });
    });
    $('#coins-table-xs').DataTable({
        paging: false,
        searching: false,
        "info": false,
        "order": [
            [2, "desc"]
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

    // // Format SM (SMALL) table to provide sort feature
    // $('#coins-table-sm').DataTable({
    //     paging: false,
    //     searching: false,
    //     "info": false,
    //     "order": [
    //         [2, "desc"]
    //     ]
    // });
    // $('.dataTables_wrapper').find('label').each(function() {
    //     $(this).parent().append($(this).children());
    // });
    // $('.dataTables_filter').find('input').each(function() {
    //     $('input').attr("placeholder", "Search");
    //     $('input').removeClass('form-control-sm');
    // });
    // $('.dataTables_length').addClass('d-flex flex-row');
    // $('.dataTables_filter').addClass('md-form');
    // $('select').addClass('mdb-select');
    // // $('.mdb-select').material_select();
    // $('.mdb-select').removeClass('form-control form-control-sm');
    // $('.dataTables_filter').find('label').remove();
    //
    // // Format MD (MEDIUM) table to provide sort feature
    // $('#coins-table-md').DataTable({
    //     paging: false,
    //     searching: false,
    //     "info": false,
    //     "order": [
    //         [2, "desc"]
    //     ]
    // });
    // $('.dataTables_wrapper').find('label').each(function() {
    //     $(this).parent().append($(this).children());
    // });
    // $('.dataTables_filter').find('input').each(function() {
    //     $('input').attr("placeholder", "Search");
    //     $('input').removeClass('form-control-sm');
    // });
    // $('.dataTables_length').addClass('d-flex flex-row');
    // $('.dataTables_filter').addClass('md-form');
    // $('select').addClass('mdb-select');
    // // $('.mdb-select').material_select();
    // $('.mdb-select').removeClass('form-control form-control-sm');
    // $('.dataTables_filter').find('label').remove();
    //
    // // Format LG & XL (LARGE AND EXTRA-LARGE) table to provide sort feature
    // $('#coins-table-lg').DataTable({
    //     paging: false,
    //     searching: false,
    //     "info": false,
    //     "order": [
    //         [2, "desc"]
    //     ]
    // });
    // $('.dataTables_wrapper').find('label').each(function() {
    //     $(this).parent().append($(this).children());
    // });
    // $('.dataTables_filter').find('input').each(function() {
    //     $('input').attr("placeholder", "Search");
    //     $('input').removeClass('form-control-sm');
    // });
    // $('.dataTables_length').addClass('d-flex flex-row');
    // $('.dataTables_filter').addClass('md-form');
    // $('select').addClass('mdb-select');
    // // $('.mdb-select').material_select();
    // $('.mdb-select').removeClass('form-control form-control-sm');
    // $('.dataTables_filter').find('label').remove();
    //




    // Actions if botton 'CURR' is clicked
    $('#btn-curr').on('click', function() {
        if (!$(this).hasClass("btn-active")) {
            // Update botton colors
            $(this).removeClass('btn-normal').addClass('btn-active')
            $('#btn-btc').removeClass('btn-active').addClass('btn-normal')
            // Select columns to display
            $('th[data-curr=curr]').each(function(i, cell) {
                $(this).removeClass('hidden-col');
            });
            $('td[data-curr=curr]').each(function(i, cell) {
                $(this).removeClass('hidden-col');
            });
            $('th[data-curr=btc]').each(function(i, cell) {
                $(this).addClass('hidden-col');
            });
            $('td[data-curr=btc]').each(function(i, cell) {
                $(this).addClass('hidden-col');
            });
        }
    });

    // Actions if botton 'BTC' is clicked
    $('#btn-btc').on('click', function() {
        if (!$(this).hasClass("btn-active")) {
            // Update botton colors
            $(this).removeClass('btn-normal').addClass('btn-active')
            $('#btn-curr').removeClass('btn-active').addClass('btn-normal')
            // Select columns to display
            $('th[data-curr=btc]').each(function(i, cell) {
                $(this).removeClass('hidden-col');
            });
            $('td[data-curr=btc]').each(function(i, cell) {
                $(this).removeClass('hidden-col');
            });
            $('th[data-curr=curr]').each(function(i, cell) {
                $(this).addClass('hidden-col');
            });
            $('td[data-curr=curr]').each(function(i, cell) {
                $(this).addClass('hidden-col');
            });
        }
    });

    function color_table() {
        // Format table contents (red/green colors)
        $('.color-sign').each(function(i, cell) {
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
                    $(this).html('-');
                    $(this).css({
                        color: 'black'
                    });
                }

            }
        });
    }

    color_table();



});