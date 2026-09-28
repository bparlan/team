theteam.advisory - the advisory layer (M5).

The team reads the user's real OMP session and speaks when there is something
to say. This package owns session reading, member selection, and the
commentary controller. It depends on nothing above it in the layer stack
(ARCHITECTURE.md §5.1): no execution internals, no CLI.