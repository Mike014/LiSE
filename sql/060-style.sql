-- This file is part of LiSE, a framework for life simulation games.
-- Copyright (c) 2013 Zachary Spector,  zacharyspector@gmail.com
INSERT INTO style
(name, fontface, fontsize, spacing, textcolor,
bg_inactive, bg_active, fg_inactive, fg_active) VALUES
    ('BigDark',
     'Sans', 20, 6,
     'solarized-base0',
     'solarized-base03',
     'solarized-base2',
     'solarized-base1',
     'solarized-base01'),
    ('SmallDark',
     'Sans', 16, 3, 
     'solarized-base0',
     'solarized-base03',
     'solarized-base2',
     'solarized-base1',
     'solarized-base01'),
    ('BigLight',
     'Sans', 20, 6,
     'solarized-base00',
     'solarized-base3',
     'solarized-base02',
     'solarized-base01',
     'solarized-base1'),
    ('SmallLight',
     'Sans', 16, 3,
     'solarized-base00',
     'solarized-base3',
     'solarized-base02',
     'solarized-base01',
     'solarized-base1'),
    ('default_style',
     'Sans', 20, 6,
     'solarized-base00',
     'solarized-base3',
     'solarized-base02',
     'solarized-base01',
     'solarized-base1');
