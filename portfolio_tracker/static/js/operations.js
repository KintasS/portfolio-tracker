$(document).ready(function() {


    // Format table to provide sort feature
    $('#operations-table').DataTable({
        // "lengthMenu": [
        //     [25, 50, 100, -1],
        //     [25, 50, 100, "All"]
        // ],
        // "displayLength": 50
        paging: false,
        // searching: false,
        // "info": false,
        "order": [
            [1, "asc"]
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
                type: 'column'
            }
        },
        columnDefs: [{
            className: 'control',
            orderable: false,
            targets: 0
        }]
    });


    //Event to trigger when Delete Entry Modal is about to be shown
    $('a[data-modal-link=deleteEntryModal]').on('click', function() {
        // Pass operation content to modal
        var opContent = $(this).data('operation');
        $('#deleted-operation').html(opContent);
        // Pass operation ID to modal
        var opID = $(this).parent().parent().attr('data-op-id');
        console.log(opID);
        var action = $('#deleteEntryModal form').attr('action').replace('99999999', opID);
        $('#deleteEntryModal form').attr('action', action);
        console.log(action);

    });

    // Hide button in consistency modal to avoid double clicking
    $('#ConsistencyModal .modal-footer a').on('click', function() {
        $(this).fadeOut();
        $('#ConsistencyModal button').fadeOut();
    });


});