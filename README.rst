=======
Striker
=======

Striker is a deployment package builder, capable of building packages
in several different formats, running basic tests on those packages,
and distributing them.  It is a tool for managing the build and
release lifecycle.

Packaging
=========

Why another packaging tool?  After all, the Python world already has
eggs and wheels, and they work really well, right?  Well, yes and no.
A wheel (or the older egg) contains a single package and information
about its dependencies.  Installing a full project onto a system
requires that several wheels be downloaded and installed, and we often
have dependencies on the exact versions that are used--i.e., which
exact versions have we performed acceptance tests against?  Also, when
you're talking about installing a package across several thousand
machines, just downloading all those dependencies represents an
enormous network load.

Striker is intended to help with this problem.  The packages it builds
include all of the dependencies into a single artifact, which can then
be distributed to those several thousand systems in a much more
scalable fashion, such as a peer-to-peer system like BitTorrent.
