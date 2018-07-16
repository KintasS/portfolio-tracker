$(document).ready(function() {

    // Paint numbers red/green
    $('#pnl-operation-table .color-sign').each(function(i, cell) {
        content = $(this).text();
        if (content.length > 2) {
            num = parseFloat(content.substr(0, content.length - 2));
            if (num < 0) {
                $(this).css({
                    color: 'red'
                    // 'font-weight': 'bold'
                });
            } else if (num > 0) {
                $(this).css({
                    color: 'green'
                    // 'font-weight': 'bold'
                });
            }
        }
    });



    // Format table to provide sort feature
    $('#pnl-operation-table').DataTable({
        // "lengthMenu": [
        //     [25, 50, 100, -1],
        //     [25, 50, 100, "All"]
        // ],
        // "displayLength": 50
        paging: false,
        // searching: false,
        // "info": false,
        "order": [
            [0, "desc"]
        ],
        "language": {
            "zeroRecords": "No se han encontrado registros",
            "info": "_TOTAL_ registros",
            "infoEmpty": "No se han encontrado registros",
            "infoFiltered": "(filtrados de _MAX_ registros)",
            "search": "Buscar:"
        },
        responsive: {
            details: {
                type: 'column',
                target: -1
            }
        },
        columnDefs: [{
            className: 'control',
            orderable: false,
            targets: -1
        }]
        // responsive: {
        //     details: {
        //         display: $.fn.dataTable.Responsive.display.modal({
        //             header: function(row) {
        //                 var data = row.data();
        //                 // return 'Detalle P&LP&G para la operación ' + data[0] + ' | ' + data[1] + ' | ' + data[2];
        //                 return 'Detalle P&L:';
        //             }
        //         }),
        //         renderer: $.fn.dataTable.Responsive.renderer.tableAll(),
        //     }
        // },
        // columnDefs: [{
        //     className: 'control',
        //     orderable: false,
        //     targets: -1
        // }]
    });
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
    // $('.mdb-select').removeClass('form-control form-control-sm');
    // $('.dataTables_filter').find('label').remove();



});