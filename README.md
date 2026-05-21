# tui-app
Quick and dirty TUI app framework for tables and forms.  Works well on RPI Zero 2 W.

OVERVIEW

Provides simple TUI table view (list of rows), and single row form for viewing/editing.  While textual is
quite slow on a Raspberry Pi Zero 2 W, this performs quite well.

Can be used in conjunction with https://github.com/dangyogi/csv-app which uses a single csv file to store
multiple tables as a crude database.

This framework interfaces to three kinds of classes that you write in your app:

table:
    .name
    .columns               # list of column objects (see below)
    .table_commands        # list of commands for table screen popup
    .row_commands          # list of commands for row popup on table screen
    .get_rows(**select)    # returns list of row objects (see below)
    .execute(app, command) # to implement commands in table_commands.
                           # (tables and 'Exit' are implemented by the framework)

column:
    .name
    .abbr                  # used if data values are short and screen width space is tight.  May be None.
    .min_width             # used for column width.  Longer data values are truncated, ending in '>'.
    .alignment             # "left" or "right"
    .can_edit              # True/False

row:
    .table_name
    .columns
    .human_key()           # human readable primary key to identify a row in the table.
    .get(column_name)      # returns human readable string.
    .delete()
    .update(**kws)
    .execute(app, command) # for anything other than View/Edit/Delete
