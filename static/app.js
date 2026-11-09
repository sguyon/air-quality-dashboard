// Home Air Quality: data, readings, summary, charts, header panels.
const ICONS = {"toddler":"<svg class=\"i\" viewBox=\"0 0 24 24\" aria-hidden=\"true\"><path d=\"M10 16c.5.3 1.2.5 2 .5s1.5-.2 2-.5\"/><path d=\"M15 12h.01\"/><path d=\"M19.38 6.813A9 9 0 0 1 20.8 10.2a2 2 0 0 1 0 3.6 9 9 0 0 1-17.6 0 2 2 0 0 1 0-3.6A9 9 0 0 1 12 3c2 0 3.5 1.1 3.5 2.5s-.9 2.5-2 2.5c-.8 0-1.5-.4-1.5-1\"/><path d=\"M9 12h.01\"/></svg>","sinus":"<svg class=\"i\" viewBox=\"0 0 24 24\" aria-hidden=\"true\"><path d=\"M12.8 19.6A2 2 0 1 0 14 16H2\"/><path d=\"M17.5 8a2.5 2.5 0 1 1 2 4H2\"/><path d=\"M9.8 4.4A2 2 0 1 1 11 8H2\"/></svg>","runner":"<svg class=\"i\" viewBox=\"0 0 24 24\" aria-hidden=\"true\"><circle cx=\"13\" cy=\"4\" r=\"1\"/><path d=\"M4 17l5 1l.75-1.5\"/><path d=\"M15 21v-4l-4-3l1-6\"/><path d=\"M7 12V9l5-1l3 3l3 1\"/></svg>","drop":"<svg class=\"i\" viewBox=\"0 0 24 24\" aria-hidden=\"true\"><path d=\"M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z\"/></svg>","one":"<svg aria-hidden=\"true\" viewBox=\"0 0 48 48\" width=\"44\" height=\"44\" shape-rendering=\"geometricPrecision\"> <defs> <linearGradient id=\"hw8face\" x1=\"0\" y1=\"0\" x2=\".35\" y2=\"1\"><stop offset=\"0\" stop-color=\"#fbfbfc\"/><stop offset=\"1\" stop-color=\"#e9ebee\"/></linearGradient> <linearGradient id=\"hw8edge\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"1\"><stop offset=\"0\" stop-color=\"#d5d9de\"/><stop offset=\"1\" stop-color=\"#bfc5cc\"/></linearGradient> <linearGradient id=\"hw8oled\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"1\"><stop offset=\"0\" stop-color=\"#14171c\"/><stop offset=\"1\" stop-color=\"#05070a\"/></linearGradient> <radialGradient id=\"hw8sh\" cx=\".5\" cy=\".5\" r=\".5\"><stop offset=\"0\" stop-color=\"#0f172a\" stop-opacity=\".22\"/><stop offset=\"1\" stop-color=\"#0f172a\" stop-opacity=\"0\"/></radialGradient> </defs> <ellipse cx=\"24\" cy=\"42.6\" rx=\"18\" ry=\"2.4\" fill=\"url(#hw8sh)\"/> <rect x=\"5\" y=\"8.5\" width=\"38\" height=\"33\" rx=\"8\" fill=\"url(#hw8edge)\"/> <g fill=\"#aab1b9\"><rect x=\"11\" y=\"38.6\" width=\"5\" height=\".9\" rx=\".45\"/><rect x=\"18.5\" y=\"38.6\" width=\"5\" height=\".9\" rx=\".45\"/><rect x=\"26\" y=\"38.6\" width=\"5\" height=\".9\" rx=\".45\"/><rect x=\"33.5\" y=\"38.6\" width=\"4\" height=\".9\" rx=\".45\"/></g> <rect x=\"5\" y=\"5.5\" width=\"38\" height=\"32.5\" rx=\"8\" fill=\"url(#hw8face)\" stroke=\"#d3d8de\" stroke-width=\".6\"/> <path d=\"M12.5 6.25h23a7.4 7.4 0 0 1 4.6 1.6\" stroke=\"#ffffff\" stroke-width=\".7\" stroke-linecap=\"round\" fill=\"none\" opacity=\".8\"/> <g> <circle cx=\"11.6\" cy=\"11.6\" r=\"1.05\" fill=\"#22c55e\"/><circle cx=\"14.1\" cy=\"11.6\" r=\"1.05\" fill=\"#22c55e\"/><circle cx=\"16.6\" cy=\"11.6\" r=\"1.05\" fill=\"#2fc95b\"/> <circle cx=\"19.1\" cy=\"11.6\" r=\"1.05\" fill=\"#4ccf55\"/><circle cx=\"21.6\" cy=\"11.6\" r=\"1.05\" fill=\"#74d34c\"/><circle cx=\"24.1\" cy=\"11.6\" r=\"1.05\" fill=\"#a3d642\"/> <circle cx=\"26.6\" cy=\"11.6\" r=\"1.05\" fill=\"#cdd23a\"/><circle cx=\"29.1\" cy=\"11.6\" r=\"1.05\" fill=\"#f2c537\"/><circle cx=\"31.6\" cy=\"11.6\" r=\"1.05\" fill=\"#f6ab35\"/> <circle cx=\"34.1\" cy=\"11.6\" r=\"1.05\" fill=\"#f59234\"/><circle cx=\"36.6\" cy=\"11.6\" r=\"1.05\" fill=\"#d9dde2\"/> </g> <g fill=\"#ffffff\" opacity=\".55\"><circle cx=\"11.3\" cy=\"11.2\" r=\".3\"/><circle cx=\"19.0\" cy=\"11.2\" r=\".3\"/><circle cx=\"26.5\" cy=\"11.2\" r=\".3\"/><circle cx=\"34.0\" cy=\"11.2\" r=\".3\"/></g> <rect x=\"23.5\" y=\"17\" width=\"14.5\" height=\"9.6\" rx=\"1.2\" fill=\"url(#hw8oled)\" stroke=\"#2a2f37\" stroke-width=\".5\"/> <g fill=\"#eef3f8\"> <rect x=\"25\" y=\"18.8\" width=\"7.6\" height=\"1\" rx=\".35\"/><rect x=\"25\" y=\"20.8\" width=\"5.6\" height=\"1\" rx=\".35\"/> <rect x=\"25\" y=\"22.8\" width=\"6.8\" height=\"1\" rx=\".35\"/><rect x=\"25\" y=\"24.6\" width=\"4.8\" height=\".8\" rx=\".35\" opacity=\".7\"/> </g> <rect x=\"33.8\" y=\"18.8\" width=\"2.6\" height=\"1\" rx=\".35\" fill=\"#7fd3e6\"/> <g fill=\"none\" stroke=\"#8d949c\" stroke-linecap=\"round\"><path d=\"M11.61 31.70A1.67 1.67 0 1 0 11.61 34.52\" stroke-width=\"0.41\"/><path d=\"M11.10 32.19A1.04 1.04 0 1 0 11.10 34.03\" stroke-width=\"0.24\" opacity=\".8\"/></g><text x=\"10.20\" y=\"34.00\" font-family=\"Inter, Helvetica, Arial, sans-serif\" font-size=\"2.70\" fill=\"#8d949c\" letter-spacing=\"-.04\"><tspan font-weight=\"700\" fill=\"#7b828a\">air</tspan><tspan font-weight=\"500\">gradient</tspan></text> </svg>","openair":"<svg aria-hidden=\"true\" viewBox=\"0 0 48 48\" width=\"44\" height=\"44\"> <defs> <linearGradient id=\"hw6shell\" x1=\"0\" y1=\"0\" x2=\"1\" y2=\"0\"><stop offset=\"0\" stop-color=\"#eef1f5\"/><stop offset=\".35\" stop-color=\"#ffffff\"/><stop offset=\"1\" stop-color=\"#dfe4ea\"/></linearGradient> <linearGradient id=\"hw6shellTop\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"1\"><stop offset=\"0\" stop-color=\"#ffffff\" stop-opacity=\".5\"/><stop offset=\"1\" stop-color=\"#ffffff\" stop-opacity=\"0\"/></linearGradient> <linearGradient id=\"hw6base\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"1\"><stop offset=\"0\" stop-color=\"#3d8ee6\"/><stop offset=\"1\" stop-color=\"#1f62c4\"/></linearGradient> <radialGradient id=\"hw6shadow\" cx=\".5\" cy=\".5\" r=\".5\"><stop offset=\"0\" stop-color=\"#0f172a\" stop-opacity=\".22\"/><stop offset=\"1\" stop-color=\"#0f172a\" stop-opacity=\"0\"/></radialGradient> </defs> <ellipse cx=\"24\" cy=\"42.6\" rx=\"18\" ry=\"2.4\" fill=\"url(#hw6shadow)\"/><g transform=\"translate(0 2.6)\"> <path d=\"M27.6 37.5c0 3 1.6 4.6 5 6.4\" stroke=\"#8e98a3\" stroke-width=\"2\" fill=\"none\" stroke-linecap=\"round\"/> <path d=\"M27.6 37.5c0 3 1.6 4.6 5 6.4\" stroke=\"#d6dce3\" stroke-width=\".8\" fill=\"none\" stroke-linecap=\"round\" transform=\"translate(-.35 -.2)\"/> <rect x=\"7.6\" y=\"31\" width=\"32.8\" height=\"7.6\" rx=\"3.3\" fill=\"url(#hw6base)\"/> <rect x=\"9\" y=\"32.2\" width=\"30\" height=\"1.2\" rx=\".6\" fill=\"#ffffff\" opacity=\".28\"/> <path d=\"M8.2 31.2V15.5C8.2 11 11 8 15.5 8h17C37 8 39.8 11 39.8 15.5v15.7c0 .5-.4.8-.9.8h-1.6c-.8 0-1.3-.4-1.6-1.1-.4-.9-1.1-1.5-2.1-1.5H14.4c-1 0-1.7.6-2.1 1.5-.3.7-.8 1.1-1.6 1.1H9c-.5 0-.8-.3-.8-.8z\" fill=\"url(#hw6shell)\" stroke=\"#c6ced7\" stroke-width=\".8\" stroke-linejoin=\"round\"/> <path d=\"M9.4 15.3C9.4 11.8 11.8 9.3 15.5 9.3h17c3.7 0 6.1 2.5 6.1 6v3H9.4z\" fill=\"url(#hw6shellTop)\"/> <path d=\"M12.5 9.6h23\" stroke=\"#ffffff\" stroke-width=\"1\" stroke-linecap=\"round\" opacity=\".95\"/> <g fill=\"none\" stroke=\"#8d949c\" stroke-linecap=\"round\"><path d=\"M18.16 23.85A1.86 1.86 0 1 0 18.16 26.97\" stroke-width=\"0.45\"/><path d=\"M17.61 24.39A1.15 1.15 0 1 0 17.61 26.43\" stroke-width=\"0.27\" opacity=\".8\"/></g><text x=\"16.60\" y=\"26.40\" font-family=\"Inter, Helvetica, Arial, sans-serif\" font-size=\"3.00\" fill=\"#8d949c\" letter-spacing=\"-.04\"><tspan font-weight=\"700\" fill=\"#7b828a\">air</tspan><tspan font-weight=\"500\">gradient</tspan></text> </g></svg>","sceneIn":"<svg class=\"mc-scene\" aria-hidden=\"true\" xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 120 88\"><defs><linearGradient id=\"sci15sky\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"1\"><stop offset=\"0\" style=\"stop-color:var(--scene-top,#c9dcf4)\"/><stop offset=\"1\" style=\"stop-color:var(--scene-hor,#e6eef9)\"/></linearGradient><clipPath id=\"sci15g\"><rect x=\"46\" y=\"14\" width=\"34\" height=\"46\"/></clipPath></defs><rect x=\"26\" y=\"6\" width=\"74\" height=\"1.6\" rx=\".8\" fill=\"#d6d0c6\"/><path d=\"M40 8h46v58H40z\" fill=\"#eadfcd\"/><path d=\"M40 8l6 6v46l-6 6zM86 8l-6 6v46l6 6z\" fill=\"#d9c8ac\"/><path d=\"M40 8h46l-6 6H46z\" fill=\"#d2bf9f\"/><rect x=\"46\" y=\"14\" width=\"34\" height=\"46\" fill=\"url(#sci15sky)\"/><g clip-path=\"url(#sci15g)\"><path style=\"fill:var(--sky-city,#9fb0c8)\" opacity=\".38\" d=\"M46 60V48l5-4 5 4v-3h7v-5l6 5v-2h5l6 5v12z\"/><circle cx=\"53\" cy=\"47\" r=\"5\" fill=\"#9fb59a\" opacity=\".55\"/><path d=\"M53 51v9\" stroke=\"#9fb59a\" stroke-width=\"1.2\" opacity=\".55\"/></g><g clip-path=\"url(#sci15g)\"><g class=\"wx-lit\" fill=\"#ffd98a\"><rect x=\"57.5\" y=\"50\" width=\"1.2\" height=\"1.2\"/><rect x=\"64.6\" y=\"45\" width=\"1.2\" height=\"1.2\"/><rect x=\"64.6\" y=\"49\" width=\"1.2\" height=\"1.2\"/><rect x=\"71\" y=\"52\" width=\"1.2\" height=\"1.2\"/><rect x=\"51\" y=\"55\" width=\"1.2\" height=\"1.2\"/></g><g class=\"wx-c\" fill=\"#ffffff\" opacity=\".75\"><ellipse cx=\"54\" cy=\"20\" rx=\"8\" ry=\"3.4\"/><ellipse cx=\"60\" cy=\"18.4\" rx=\"6\" ry=\"3.6\"/><ellipse cx=\"72\" cy=\"24\" rx=\"7\" ry=\"2.8\"/></g><g class=\"wx-r\" stroke=\"#7d93b5\" stroke-width=\".55\" stroke-linecap=\"round\"><g class=\"wx-fall\"><path d=\"M55.0 5.0l-1.2 4.7\" opacity=\"0.52\"/><path d=\"M48.5 19.3l-1.2 6.3\" opacity=\"0.81\"/><path d=\"M75.1 10.7l-1.2 5.1\" opacity=\"0.57\"/><path d=\"M52.6 5.1l-1.2 4.1\" opacity=\"0.87\"/><path d=\"M77.5 38.7l-1.2 5.9\" opacity=\"0.54\"/><path d=\"M57.8 30.1l-1.2 5.7\" opacity=\"0.83\"/><path d=\"M79.4 4.2l-1.2 5.3\" opacity=\"0.75\"/><path d=\"M65.2 8.5l-1.2 4.9\" opacity=\"0.49\"/><path d=\"M81.5 41.5l-1.2 5.1\" opacity=\"0.59\"/><path d=\"M80.5 27.5l-1.2 6.1\" opacity=\"0.83\"/><path d=\"M65.3 19.9l-1.2 5.3\" opacity=\"0.64\"/><path d=\"M52.1 14.6l-1.2 5.9\" opacity=\"0.47\"/><path d=\"M47.8 30.1l-1.2 4.3\" opacity=\"0.69\"/><path d=\"M63.9 16.5l-1.2 6.5\" opacity=\"0.54\"/><path d=\"M61.7 9.7l-1.2 5.4\" opacity=\"0.57\"/><path d=\"M59.5 35.9l-1.2 4.5\" opacity=\"0.70\"/><path d=\"M80.4 4.8l-1.2 3.7\" opacity=\"0.55\"/><path d=\"M75.1 29.5l-1.2 4.2\" opacity=\"0.60\"/><path d=\"M52.7 22.0l-1.2 3.6\" opacity=\"0.76\"/><path d=\"M80.0 45.8l-1.2 5.7\" opacity=\"0.88\"/><path d=\"M46.7 13.9l-1.2 6.4\" opacity=\"0.80\"/><path d=\"M61.6 45.3l-1.2 5.4\" opacity=\"0.82\"/><path d=\"M57.1 9.2l-1.2 4.8\" opacity=\"0.51\"/><path d=\"M60.5 46.2l-1.2 4.5\" opacity=\"0.45\"/><path d=\"M47.7 8.1l-1.2 5.9\" opacity=\"0.61\"/><path d=\"M57.0 4.7l-1.2 6.4\" opacity=\"0.64\"/><g transform=\"translate(0 -48)\"><path d=\"M55.0 5.0l-1.2 4.7\" opacity=\"0.52\"/><path d=\"M48.5 19.3l-1.2 6.3\" opacity=\"0.81\"/><path d=\"M75.1 10.7l-1.2 5.1\" opacity=\"0.57\"/><path d=\"M52.6 5.1l-1.2 4.1\" opacity=\"0.87\"/><path d=\"M77.5 38.7l-1.2 5.9\" opacity=\"0.54\"/><path d=\"M57.8 30.1l-1.2 5.7\" opacity=\"0.83\"/><path d=\"M79.4 4.2l-1.2 5.3\" opacity=\"0.75\"/><path d=\"M65.2 8.5l-1.2 4.9\" opacity=\"0.49\"/><path d=\"M81.5 41.5l-1.2 5.1\" opacity=\"0.59\"/><path d=\"M80.5 27.5l-1.2 6.1\" opacity=\"0.83\"/><path d=\"M65.3 19.9l-1.2 5.3\" opacity=\"0.64\"/><path d=\"M52.1 14.6l-1.2 5.9\" opacity=\"0.47\"/><path d=\"M47.8 30.1l-1.2 4.3\" opacity=\"0.69\"/><path d=\"M63.9 16.5l-1.2 6.5\" opacity=\"0.54\"/><path d=\"M61.7 9.7l-1.2 5.4\" opacity=\"0.57\"/><path d=\"M59.5 35.9l-1.2 4.5\" opacity=\"0.70\"/><path d=\"M80.4 4.8l-1.2 3.7\" opacity=\"0.55\"/><path d=\"M75.1 29.5l-1.2 4.2\" opacity=\"0.60\"/><path d=\"M52.7 22.0l-1.2 3.6\" opacity=\"0.76\"/><path d=\"M80.0 45.8l-1.2 5.7\" opacity=\"0.88\"/><path d=\"M46.7 13.9l-1.2 6.4\" opacity=\"0.80\"/><path d=\"M61.6 45.3l-1.2 5.4\" opacity=\"0.82\"/><path d=\"M57.1 9.2l-1.2 4.8\" opacity=\"0.51\"/><path d=\"M60.5 46.2l-1.2 4.5\" opacity=\"0.45\"/><path d=\"M47.7 8.1l-1.2 5.9\" opacity=\"0.61\"/><path d=\"M57.0 4.7l-1.2 6.4\" opacity=\"0.64\"/></g></g></g><g class=\"wx-r\" fill=\"#ffffff\" opacity=\".7\"><circle cx=\"50\" cy=\"30\" r=\".7\"/><circle cx=\"57\" cy=\"44\" r=\".55\"/><circle cx=\"68\" cy=\"26\" r=\".6\"/><circle cx=\"74\" cy=\"40\" r=\".75\"/><circle cx=\"66\" cy=\"52\" r=\".5\"/><circle cx=\"52\" cy=\"54\" r=\".6\"/></g></g><rect x=\"46\" y=\"14\" width=\"34\" height=\"46\" fill=\"none\" stroke=\"#3a3530\" stroke-width=\"1.4\"/><path d=\"M63 14v46M46 37h34\" stroke=\"#3a3530\" stroke-width=\"1\"/><path d=\"M40 66h46l5 5H35z\" fill=\"#f4ede1\"/><rect x=\"35\" y=\"71\" width=\"56\" height=\"1.6\" fill=\"#ddd2c0\"/><rect x=\"49\" y=\"60.6\" width=\"8\" height=\"5.6\" rx=\"1.5\" fill=\"#fbfbfc\" stroke=\"#cdd2d8\" stroke-width=\".4\"/><path d=\"M50.6 62.1h4.8\" stroke=\"#8cc98f\" stroke-width=\".8\" stroke-linecap=\"round\" stroke-dasharray=\".1 1\"/><rect x=\"53.4\" y=\"63.2\" width=\"2.4\" height=\"1.6\" rx=\".3\" fill=\"#2a2d32\"/><path d=\"M70 66l.8-5h5.4l.8 5z\" fill=\"#cf9b78\"/><path d=\"M73.5 61c-.5-3 .5-5 2.5-6-.5 2-1 4-2.5 6zM73.5 61c-1.5-2-3.5-3-5.5-3 1.5 2 3.5 2.6 5.5 3z\" fill=\"#7aa784\"/><path d=\"M30 8h12c0 26 0 52-1 80H27c2-28 3-54 3-80z\" fill=\"#e6d8c0\"/><path d=\"M96 8H84c0 26 0 52 1 80h14c-2-28-3-54-3-80z\" fill=\"#e6d8c0\"/><g class=\"sig\"><circle cx=\"53\" cy=\"63.4\" r=\"3\" fill=\"none\" stroke=\"#4f86d6\" stroke-width=\".6\" opacity=\"0\"><animate attributeName=\"r\" values=\"3;12;12\" keyTimes=\"0;.36;1\" dur=\"7s\" begin=\"0s\" repeatCount=\"indefinite\"/><animate attributeName=\"opacity\" values=\"0;.85;0;0\" keyTimes=\"0;.04;.36;1\" dur=\"7s\" begin=\"0s\" repeatCount=\"indefinite\"/></circle><circle cx=\"53\" cy=\"63.4\" r=\"3\" fill=\"none\" stroke=\"#4f86d6\" stroke-width=\".6\" opacity=\"0\"><animate attributeName=\"r\" values=\"3;12;12\" keyTimes=\"0;.36;1\" dur=\"7s\" begin=\"0.7s\" repeatCount=\"indefinite\"/><animate attributeName=\"opacity\" values=\"0;.85;0;0\" keyTimes=\"0;.04;.36;1\" dur=\"7s\" begin=\"0.7s\" repeatCount=\"indefinite\"/></circle></g></svg>","sceneOut":"<svg class=\"mc-scene\" aria-hidden=\"true\" xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 120 88\"><defs><linearGradient id=\"sco15glass\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"1\"><stop offset=\"0\" style=\"stop-color:var(--scene-top,#c9dcf4)\"/><stop offset=\"1\" style=\"stop-color:var(--scene-hor,#e6eef9)\"/></linearGradient></defs><rect x=\"0\" y=\"12\" width=\"120\" height=\"56\" fill=\"#f5f3ef\"/><rect x=\"94\" y=\"12\" width=\"26\" height=\"56\" fill=\"#e3d2bb\"/><path d=\"M99 12v56M104 12v56M109 12v56M114 12v56\" stroke=\"#d6c2a6\" stroke-width=\".6\"/><rect x=\"0\" y=\"9\" width=\"120\" height=\"3.2\" fill=\"#4a4d52\"/><rect x=\"0\" y=\"12.2\" width=\"120\" height=\"1.2\" fill=\"#e4e1db\"/><rect x=\"38\" y=\"17\" width=\"54\" height=\"40\" fill=\"url(#sco15glass)\"/><rect class=\"wx-n\" x=\"38\" y=\"17\" width=\"54\" height=\"40\" fill=\"#f7e2b4\"/><path d=\"M41 17h7L39 38V20z\" fill=\"#ffffff\" opacity=\".3\"/><rect x=\"38\" y=\"17\" width=\"54\" height=\"40\" fill=\"none\" stroke=\"#45484d\" stroke-width=\"1.1\"/><path d=\"M56 17v40M74 17v40\" stroke=\"#45484d\" stroke-width=\".8\"/><path d=\"M95.6 36.4v-2.6c0-1.6 1-2.4 2.4-2.4h2.2c1.4 0 2.4.8 2.4 2.4v2.6z\" fill=\"#ffffff\" stroke=\"#cdd2d8\" stroke-width=\".4\"/><rect x=\"95.4\" y=\"36\" width=\"7.4\" height=\"1.6\" rx=\".6\" fill=\"#5b8fd9\"/><rect x=\"36\" y=\"57\" width=\"58\" height=\"4\" fill=\"#efebe5\"/><rect x=\"32\" y=\"61\" width=\"66\" height=\"4\" fill=\"#e7e2da\"/><rect x=\"28\" y=\"65\" width=\"74\" height=\"4.4\" fill=\"#dfd9cf\"/><path d=\"M36 57.2h58M32 61.2h66M28 65.2h74\" stroke=\"#b9b1a5\" stroke-width=\".7\"/><rect x=\"0\" y=\"69.2\" width=\"120\" height=\"18.8\" fill=\"#a7c19c\"/><circle cx=\"22\" cy=\"65\" r=\"5.4\" fill=\"#93ae8a\"/><circle cx=\"17\" cy=\"67\" r=\"3.6\" fill=\"#9db897\"/><path class=\"wx-dark\" fill-rule=\"evenodd\" d=\"M0 0h120v88H0zM38 17v40h54V17z\" fill=\"#1c2747\"/><g class=\"wx-c\" fill=\"#ffffff\" opacity=\".85\"><ellipse cx=\"52\" cy=\"4.6\" rx=\"9\" ry=\"3.2\"/><ellipse cx=\"60\" cy=\"3.4\" rx=\"6\" ry=\"3.2\"/><ellipse cx=\"84\" cy=\"5\" rx=\"7\" ry=\"2.6\"/></g><g class=\"wx-r\" stroke=\"#7d93b5\" stroke-width=\".55\" stroke-linecap=\"round\"><g class=\"wx-fall\"><path d=\"M46.7 4.5l-1.2 3.7\" opacity=\"0.53\"/><path d=\"M88.9 11.4l-1.2 3.6\" opacity=\"0.67\"/><path d=\"M50.4 75.8l-1.2 3.9\" opacity=\"0.69\"/><path d=\"M97.6 31.1l-1.2 6.5\" opacity=\"0.66\"/><path d=\"M49.8 31.2l-1.2 3.6\" opacity=\"0.64\"/><path d=\"M50.4 67.6l-1.2 6.0\" opacity=\"0.67\"/><path d=\"M30.8 19.3l-1.2 4.2\" opacity=\"0.54\"/><path d=\"M48.8 66.1l-1.2 3.9\" opacity=\"0.47\"/><path d=\"M111.5 43.0l-1.2 6.5\" opacity=\"0.63\"/><path d=\"M109.1 49.7l-1.2 5.9\" opacity=\"0.79\"/><path d=\"M72.5 7.1l-1.2 4.1\" opacity=\"0.84\"/><path d=\"M109.0 70.3l-1.2 4.5\" opacity=\"0.75\"/><path d=\"M100.0 48.8l-1.2 5.9\" opacity=\"0.69\"/><path d=\"M86.9 52.1l-1.2 4.3\" opacity=\"0.87\"/><path d=\"M114.1 5.7l-1.2 6.4\" opacity=\"0.88\"/><path d=\"M88.2 3.4l-1.2 6.2\" opacity=\"0.51\"/><path d=\"M115.2 50.7l-1.2 3.7\" opacity=\"0.53\"/><path d=\"M85.2 43.3l-1.2 5.7\" opacity=\"0.87\"/><path d=\"M47.7 0.2l-1.2 6.3\" opacity=\"0.46\"/><path d=\"M106.9 8.8l-1.2 5.9\" opacity=\"0.80\"/><path d=\"M107.0 41.8l-1.2 6.1\" opacity=\"0.54\"/><path d=\"M88.4 25.1l-1.2 6.2\" opacity=\"0.80\"/><path d=\"M70.4 40.0l-1.2 3.6\" opacity=\"0.47\"/><path d=\"M81.5 37.2l-1.2 6.1\" opacity=\"0.72\"/><path d=\"M40.5 27.6l-1.2 5.8\" opacity=\"0.69\"/><path d=\"M28.9 63.7l-1.2 6.0\" opacity=\"0.49\"/><path d=\"M76.9 29.0l-1.2 5.9\" opacity=\"0.59\"/><path d=\"M49.0 37.0l-1.2 6.4\" opacity=\"0.49\"/><path d=\"M38.3 47.2l-1.2 6.2\" opacity=\"0.68\"/><path d=\"M67.1 65.2l-1.2 5.8\" opacity=\"0.48\"/><path d=\"M107.3 14.9l-1.2 4.4\" opacity=\"0.83\"/><path d=\"M66.0 60.7l-1.2 4.0\" opacity=\"0.84\"/><path d=\"M43.9 11.3l-1.2 5.0\" opacity=\"0.60\"/><path d=\"M76.8 68.7l-1.2 5.6\" opacity=\"0.45\"/><path d=\"M56.1 41.4l-1.2 5.0\" opacity=\"0.77\"/><path d=\"M71.6 5.8l-1.2 4.2\" opacity=\"0.83\"/><path d=\"M60.1 58.3l-1.2 6.5\" opacity=\"0.73\"/><path d=\"M88.9 46.3l-1.2 4.4\" opacity=\"0.86\"/><path d=\"M70.0 69.3l-1.2 4.4\" opacity=\"0.84\"/><path d=\"M98.8 46.6l-1.2 4.8\" opacity=\"0.51\"/><g transform=\"translate(0 -76)\"><path d=\"M46.7 4.5l-1.2 3.7\" opacity=\"0.53\"/><path d=\"M88.9 11.4l-1.2 3.6\" opacity=\"0.67\"/><path d=\"M50.4 75.8l-1.2 3.9\" opacity=\"0.69\"/><path d=\"M97.6 31.1l-1.2 6.5\" opacity=\"0.66\"/><path d=\"M49.8 31.2l-1.2 3.6\" opacity=\"0.64\"/><path d=\"M50.4 67.6l-1.2 6.0\" opacity=\"0.67\"/><path d=\"M30.8 19.3l-1.2 4.2\" opacity=\"0.54\"/><path d=\"M48.8 66.1l-1.2 3.9\" opacity=\"0.47\"/><path d=\"M111.5 43.0l-1.2 6.5\" opacity=\"0.63\"/><path d=\"M109.1 49.7l-1.2 5.9\" opacity=\"0.79\"/><path d=\"M72.5 7.1l-1.2 4.1\" opacity=\"0.84\"/><path d=\"M109.0 70.3l-1.2 4.5\" opacity=\"0.75\"/><path d=\"M100.0 48.8l-1.2 5.9\" opacity=\"0.69\"/><path d=\"M86.9 52.1l-1.2 4.3\" opacity=\"0.87\"/><path d=\"M114.1 5.7l-1.2 6.4\" opacity=\"0.88\"/><path d=\"M88.2 3.4l-1.2 6.2\" opacity=\"0.51\"/><path d=\"M115.2 50.7l-1.2 3.7\" opacity=\"0.53\"/><path d=\"M85.2 43.3l-1.2 5.7\" opacity=\"0.87\"/><path d=\"M47.7 0.2l-1.2 6.3\" opacity=\"0.46\"/><path d=\"M106.9 8.8l-1.2 5.9\" opacity=\"0.80\"/><path d=\"M107.0 41.8l-1.2 6.1\" opacity=\"0.54\"/><path d=\"M88.4 25.1l-1.2 6.2\" opacity=\"0.80\"/><path d=\"M70.4 40.0l-1.2 3.6\" opacity=\"0.47\"/><path d=\"M81.5 37.2l-1.2 6.1\" opacity=\"0.72\"/><path d=\"M40.5 27.6l-1.2 5.8\" opacity=\"0.69\"/><path d=\"M28.9 63.7l-1.2 6.0\" opacity=\"0.49\"/><path d=\"M76.9 29.0l-1.2 5.9\" opacity=\"0.59\"/><path d=\"M49.0 37.0l-1.2 6.4\" opacity=\"0.49\"/><path d=\"M38.3 47.2l-1.2 6.2\" opacity=\"0.68\"/><path d=\"M67.1 65.2l-1.2 5.8\" opacity=\"0.48\"/><path d=\"M107.3 14.9l-1.2 4.4\" opacity=\"0.83\"/><path d=\"M66.0 60.7l-1.2 4.0\" opacity=\"0.84\"/><path d=\"M43.9 11.3l-1.2 5.0\" opacity=\"0.60\"/><path d=\"M76.8 68.7l-1.2 5.6\" opacity=\"0.45\"/><path d=\"M56.1 41.4l-1.2 5.0\" opacity=\"0.77\"/><path d=\"M71.6 5.8l-1.2 4.2\" opacity=\"0.83\"/><path d=\"M60.1 58.3l-1.2 6.5\" opacity=\"0.73\"/><path d=\"M88.9 46.3l-1.2 4.4\" opacity=\"0.86\"/><path d=\"M70.0 69.3l-1.2 4.4\" opacity=\"0.84\"/><path d=\"M98.8 46.6l-1.2 4.8\" opacity=\"0.51\"/></g></g></g><g class=\"sig\"><circle cx=\"99\" cy=\"34.5\" r=\"3\" fill=\"none\" stroke=\"#4f86d6\" stroke-width=\".6\" opacity=\"0\"><animate attributeName=\"r\" values=\"3;12;12\" keyTimes=\"0;.36;1\" dur=\"7s\" begin=\"3.5s\" repeatCount=\"indefinite\"/><animate attributeName=\"opacity\" values=\"0;.85;0;0\" keyTimes=\"0;.04;.36;1\" dur=\"7s\" begin=\"3.5s\" repeatCount=\"indefinite\"/></circle><circle cx=\"99\" cy=\"34.5\" r=\"3\" fill=\"none\" stroke=\"#4f86d6\" stroke-width=\".6\" opacity=\"0\"><animate attributeName=\"r\" values=\"3;12;12\" keyTimes=\"0;.36;1\" dur=\"7s\" begin=\"4.2s\" repeatCount=\"indefinite\"/><animate attributeName=\"opacity\" values=\"0;.85;0;0\" keyTimes=\"0;.04;.36;1\" dur=\"7s\" begin=\"4.2s\" repeatCount=\"indefinite\"/></circle></g></svg>"};
// Each inserted copy of a drawing gets its own ids: a gradient referenced from a hidden copy doesn't paint.
let svgCopy = 0;
const uniq = svg => { const n = ++svgCopy; return svg.replace(/id="([^"]+)"/g, `id="$1-${n}"`).replace(/url\(#([^)]+)\)/g, `url(#$1-${n})`); };
// The home (place, links, road, needs, limits, pollen seasons) comes from the server's config: window.APP, set in index().
const APP = window.APP;
// A public AirGradient monitor's page (the demo's ?monitor=<id>): {id, name, street, contributor, url}. One that can't
// be shown ({id, error}) gets the default sample's page instead, with the reason in the demo banner (picker.js).
// A public monitor's view has no indoor monitor; neither has a view whose place names none (APP.place.indoor null).
const PUB = APP.public && !APP.public.error ? APP.public : null;
const NO_INDOOR = APP.place.indoor === null || !!PUB;
const VIEW_PLACE = NO_INDOOR ? { ...APP.place, indoor: null } : APP.place;   // what home.js reads to draw the indoor slot disabled
const SELF = selfWords(!!PUB);   // the neighborhood's words for the shown monitor: This / You
// The page's clock (summary.js): the demo's story moment (APP.now), or the real time. What the page shows uses it;
// timers and cache stamps keep Date.now(). The demo also names its moment, or its public monitor, on every /api call.
const appNow = SummaryCard.appNow, readingsNow = SummaryCard.readingsNow;   // readingsNow: what the readings' age is judged against
const apiUrl = url => Picker.apiUrl(APP, url);   // ?monitor=<id> on a public monitor's page, ?moment= on a sample (picker.js)
const TZ = APP.place.timezone;
const PM_FINE = APP.limits.pm, PM_HIGH = APP.limits.pm_high, CO2_OPEN = APP.limits.co2;
const RH_LOW = APP.limits.rh_dry, RH_GOOD = APP.limits.rh_good, RH_DAMP = APP.limits.rh_damp;
// Display scales, not the home's limits: the words on the monitor cards past the configured lines.
const PM_RING_MAX = 55;          // µg/m³: the PM2.5 ring is full at this reading
const CO2_EXCELLENT = 600, CO2_FAIR = 1000, CO2_POOR = 1500;   // ppm: the CO₂ card's words around the configured limit
const RH_OUT_DAMP = 80;          // %: outdoor humidity the outdoor card calls damp
const RANGE_HOURS = { '1h': 1, '6h': 6, '24h': 24, '7d': 168 };
const RANGE_LABEL = { '1h': 'Last hour', '6h': 'Last 6 hours', '24h': 'Last 24 hours', '7d': 'Last 7 days' };
const READ_MAX_AGE = 10 * 60 * 1000;
const CACHE_KEY = 'air-read-v2' + (APP.now ? ':' + APP.now.moment : '');   // the demo keeps one per moment

const state = { range: '1h', indoor: null, outdoor: null, neighbors: [], read: null, readAt: 0, readKey: '' };

const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// Fill the page's home-specific links and labels ([data-app] in index.html) from the config, once at load.
// Without a road: no road card, source row, legend or road words. Needs that are off are hidden.
function applyConfig() {
  const { place, links, road, needs } = APP;
  const set = (el, attr, v) => { if (v) el.setAttribute(attr, v); else el.removeAttribute(attr); };
  const runner = `Runner: adds the run check, saying when the outdoor air${road ? ` and ${road.name} traffic` : ''} make${road ? '' : 's'} a run worth it.`;
  const fill = {
    'place': el => { el.textContent = PUB ? PUB.street || '' : place.name; el.hidden = !!PUB && !PUB.street; },   // the pill: a monitor's street
    'home-name': el => { if (PUB) el.textContent = PUB.name; },   // the pill names the monitor, not "Home"
    'road-card': el => { el.hidden = !road && !PUB; },   // a public monitor shows the road as Off, like pollen
    'map-home': el => { el.href = links.map_home; el.textContent = place.name; },
    'nearby-about': el => { el.textContent = `Other AirGradient monitors around ${place.name}.`; },
    'forecast': el => { el.href = links.forecast; el.title = `Hourly forecast for ${place.name}, National Weather Service`; },
    'wx-about': el => { el.textContent = road ? `Open-Meteo. Wind direction changes how ${road.name} exhaust drifts.` : 'Open-Meteo.'; },
    'pollen-link': el => {   // pollen.com needs a US ZIP; without one the heading is plain text
      set(el, 'href', links.pollen); set(el, 'title', place.pollen_zip && `5-day pollen forecast for ZIP ${place.pollen_zip}, pollen.com`);
      if (!links.pollen) { el.removeAttribute('target'); const arr = el.querySelector('.k-arr'); if (arr) arr.remove(); }
    },
    'nb-map': el => { el.setAttribute('aria-label', `Map of nearby monitors${road ? ` and the ${road.name}` : ''}`); },
    'runner-tip': el => { el.dataset.tip = runner; if (el.hasAttribute('aria-label')) el.setAttribute('aria-label', runner); },
    'needs-label': el => {
      const names = { toddler: 'Toddler', sinus: 'Sinus and allergy', runner: 'Runner' };
      const on = Object.keys(names).filter(k => needs[k]).map(k => names[k]);   // for screen readers: the pill shows no need icons
      el.textContent = on.length ? 'Needs: ' + on.join(', ') : '';
    },
    'road-only': el => { el.hidden = !road; },
    'smoke-about': el => { el.textContent = smokeText(place.region); },
    'smoke-card-about': el => { el.textContent = smokeMapText(place.region); },
    'needs-for': el => { const t = needsFor(needs); el.textContent = t; el.parentElement.hidden = !t; },
    'sources-label': el => { el.setAttribute('aria-label', sourcesLabel(APP.sources, !!road, !NO_INDOOR)); },
    'monitors-title': el => { if (PUB) el.textContent = 'Monitor'; },
    'self-legend': el => { el.textContent = SELF.legend; },
  };
  if (road) Object.assign(fill, {
    'road': el => { el.textContent = roadLabel(road); },
    'road-estimate': el => { el.textContent = `${road.name} estimate`; },
    'road-estimate-title': el => { el.title = `${road.name} estimate`; },
    'road-exhaust': el => { el.textContent = `${road.name} exhaust`; },
    'road-about-label': el => { el.setAttribute('aria-label', `About the ${road.name} estimate`); },
    'traffic': el => { el.href = links.traffic; el.title = `Live traffic on the ${road.name} near ${place.name}, Google Maps`; },
    'road-clock': el => { el.textContent = roadClockText(road); },
    'road-wind': el => { el.textContent = roadWindText(road); },
  });
  document.querySelectorAll('[data-app]').forEach(el => { const f = fill[el.dataset.app]; if (f) f(el); });
  if (!road) {   // the Off road card (a public monitor's): no link, no estimate to explain
    const link = document.querySelector('[data-app="traffic"]'); if (link) { link.removeAttribute('href'); link.removeAttribute('target'); const arr = link.querySelector('.k-arr'); if (arr) arr.remove(); }
    const q = document.querySelector('[data-road-q]'); if (q) q.hidden = true;
  }
  document.querySelectorAll('[data-need]').forEach(el => { el.hidden = !needs[el.dataset.need]; });
}
applyConfig();
if ($('nb-credit')) $('nb-credit').innerHTML = creditHtml(!!APP.now);   // the demo's line, or AirGradient's credit
if (PUB && $('hist-none')) $('hist-none').innerHTML = noHistoryHTML();   // shown only if AirGradient's map has no past readings

// The demo's banner (a sample, or a public monitor's page): the samples 1 2 3, the monitor picker, Source and setup.
if ((APP.now || APP.public) && $('demo-bar') && !/[?&]shot\b/.test(location.search)) {   // not in screenshots: the README says they come from the demo
  Picker.mount($('demo-bar'), APP);
}
// Nearby monitors turned off in the config: the section says so in one line instead of showing an empty table and map.
if ((APP.sources || {}).nearby === false) {
  const lead = document.getElementById('nb-lead'), card = document.querySelector('.nb-card');
  if (lead) lead.textContent = 'Off. ' + sourceOff('nearby', 'off').line;
  if (card) card.hidden = true;
  if ($('nb-sub')) $('nb-sub').hidden = true;
}
// Zero is a real reading; only null and undefined mean missing.
const has = v => v !== null && v !== undefined && !Number.isNaN(v);
const num = (v, d = 1) => has(v) ? Number(v).toFixed(d) : '—';
// particle values: one decimal below 10 (3.9), whole numbers from 10 up (12, 148), so three digits fit the ring
const pmNum = v => { if (!has(v)) return '—'; const r = Math.round(v * 10) / 10; return Math.abs(r) >= 10 ? String(Math.round(v)) : r.toFixed(1); };
// Temperature unit, per viewer: °C unless they pick °F in the Home menu. Every reading arrives in °C.
// sky.js uses these too (it loads after this file).
const TEMP_KEY = 'aq-temp-unit';
let tempPref = 'C';
try { if (localStorage.getItem(TEMP_KEY) === 'F') tempPref = 'F'; } catch {}
const tempUnit = () => tempPref;
const toF = c => c * 9 / 5 + 32;
// fmtTemp(15.5) → "16 °C" (or "60 °F"); digits: decimals; unit: 'C' or 'F' to force one; tight: "16°C"; bare: the number only
function fmtTemp(c, { digits = 0, unit = tempPref, tight = false, bare = false } = {}) {
  if (!has(c)) return '—';
  let n = (unit === 'F' ? toF(c) : c).toFixed(digits);
  if (/^-0(\.0+)?$/.test(n)) n = n.slice(1);   // no "-0 °C"
  return bare ? n : `${n}${tight ? '' : ' '}°${unit}`;
}
const otherUnit = () => tempPref === 'F' ? 'C' : 'F';
const pick = (m, ...keys) => { for (const k of keys) if (m && has(m[k])) return m[k]; return null; };
const clock = d => new Date(d).toLocaleTimeString('en-US', { timeZone: TZ, hour: 'numeric', minute: '2-digit' });
const store = {
  get() { try { return JSON.parse(localStorage.getItem(CACHE_KEY) || 'null'); } catch { return null; } },
  set(v) { try { localStorage.setItem(CACHE_KEY, JSON.stringify(v)); } catch {} }
};

// force: the Refresh button asks the server to skip its cache (it still ignores repeats within 15 s)
let forceNext = false;
async function getJSON(url, opts = {}) {
  if (forceNext) opts = { ...opts, headers: { ...(opts.headers || {}), 'X-Force-Refresh': '1' } };
  const r = await fetch(apiUrl(url), opts);
  if (!r.ok) throw new Error(`${url} ${r.status}`);
  return r.json();
}

function homeHour() {
  return Number(appNow().toLocaleString('en-US', { timeZone: TZ, hour: 'numeric', hour12: false })) % 24;
}



// Connection status for a row in the Home panel: a dot plus a few words.
const SRC_ON = APP.sources || {};   // a source turned off in the config is not counted
const srcOk = { ...(SRC_ON.nearby !== false ? { nearby: null } : {}), wx: null, ...(SRC_ON.pollen !== false ? { pollen: null } : {}), ...(SRC_ON.smoke !== false ? { smoke: null } : {}), ...(APP.road ? { bqe: true } : {}) };
function setStatus(id, tone, text, title) {
  const el = $('st-' + id); if (!el) return;
  el.className = 'pst ' + tone; el.lastElementChild.textContent = text; el.title = title || text;
  if (tone === 'neutral' && id !== 'bqe') delete srcOk[id];   // off or not set up: not counted, not an error
  else if (id in srcOk && id !== 'bqe') srcOk[id] = tone === 'good';
}
function monitorStatus(id, m) {
  const r = monitorRow(m, readingsNow(), id === 'one' && NO_INDOOR, TZ);
  const row = $('st-' + id) && $('st-' + id).closest('.pr'); if (row) row.classList.toggle('off', r.off);   // greyed device
  setStatus(id, r.tone, r.text, r.title);
}
function sourceSummary() {
  const all = Object.keys(srcOk).length, known = Object.values(srcOk).filter(v => v !== null);
  return known.length < all ? `${all} sources` : `${known.filter(Boolean).length === all ? all : known.filter(Boolean).length + ' of ' + all} sources`;
}

function reading(m, indoor) {
  if (!m) return {};
  return {
    pm: pick(m, 'pm02_corrected', 'pm02'),
    co2: pick(m, 'rco2_corrected', 'rco2'),
    t: indoor ? pick(m, 'atmp', 'atmp_corrected') : pick(m, 'atmp_corrected', 'atmp'),
    rh: indoor ? pick(m, 'rhum', 'rhum_corrected') : pick(m, 'rhum_corrected', 'rhum')
  };
}

// ── Monitors ──────────────────────────────────────────


// Production's card structure: PM2.5 hero, then CO₂ / temperature / humidity with bars and words,
// then VOC / NOx / Wi-Fi, then the secondary particle readings.
function co2Level(v) {
  if (!has(v)) return { word: '', tone: 'muted' };
  if (v <= CO2_EXCELLENT) return { word: 'Excellent', tone: 'good' };
  if (v <= CO2_OPEN) return { word: 'Good', tone: 'good' };
  if (v <= CO2_FAIR) return { word: 'Fair — open a window soon', tone: 'warn' };
  if (v <= CO2_POOR) return { word: 'Poor — ventilate', tone: 'warn' };
  return { word: 'Bad — ventilate now', tone: 'bad' };
}
function rhLevel(v, indoor) {
  if (!has(v)) return { word: '', tone: 'muted' };
  if (!indoor) return { word: v > RH_OUT_DAMP ? 'Damp outside' : 'Outside air', tone: 'muted' };
  if (v > RH_DAMP) return { word: 'Too damp — mold risk', tone: 'warn' };
  if (v < RH_LOW) return { word: 'Too dry', tone: 'warn' };
  if (v > RH_GOOD) return { word: 'A little damp', tone: 'good' };
  return { word: 'Comfortable', tone: 'good' };
}
const TONE = { good: 'var(--good)', warn: 'var(--warn)', bad: 'var(--bad)', muted: 'var(--soft)' };

function pmRing(pm, tone) {
  const r = 34, c = 2 * Math.PI * r, pct = has(pm) ? Math.min(pm / PM_RING_MAX, 1) : 0;
  return `<div class="mc-ring"><svg viewBox="0 0 80 80" aria-hidden="true"><circle class="mc-ring-bg" cx="40" cy="40" r="${r}"/>` +
    `<circle class="mc-ring-fill" cx="40" cy="40" r="${r}" stroke="${TONE[tone]}" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${(c - pct * c).toFixed(1)}"/></svg>` +
    `<div><b style="color:${TONE[tone]}">${pmNum(pm)}</b><span>µg/m³</span></div></div>`;
}

// Temperature as a comfort scale (40–90 °F): the 68–76 °F (20–24 °C) comfort band, a dot for this monitor, a hollow mark for the other side.
// The geometry stays in °F; the tooltips use the viewer's unit.
function tempScale(tC, otherC, indoor) {
  const at = f => Math.max(0, Math.min(100, (f - 40) / 50 * 100)).toFixed(1);
  const band = tempUnit() === 'F' ? '68–76 °F' : '20–24 °C';
  const o = has(otherC) ? `<i class="ts-o" style="left:${at(toF(otherC))}%" title="${indoor ? 'Outside' : 'Inside'} ${fmtTemp(otherC)}"></i>` : '';
  return `<div class="t-scale" title="Comfort range ${band}${has(otherC) ? ` · ${indoor ? 'outside' : 'inside'} ${fmtTemp(otherC)}` : ''}"><span class="t-band" style="left:${at(68)}%;width:${(at(76) - at(68)).toFixed(1)}%"></span>${o}<i class="ts-me" style="left:${at(toF(tC))}%"></i></div>`;
}

function monitorCard(m, indoor) {
  const f = freshness(m, readingsNow()), r = reading(m, indoor);
  const pl = pmLevel(has(r.pm) ? r.pm : null, APP.limits), cl = co2Level(r.co2), hl = rhLevel(r.rh, indoor);
  const voc = m && m.tvocIndex, nox = m && m.noxIndex, wifi = PUB ? null : m && m.wifi;   // a public monitor's Wi‑Fi isn't ours to show
  // a public monitor is named by its owner's name for it, then "public monitor"; a home's by the device and its place
  const pubName = !indoor && PUB && PUB.name ? PUB.name : null;
  const what = pubName ? 'public monitor' : esc(indoor ? APP.place.indoor : APP.place.outdoor);
  const bar = (pct, tone) => `<div class="mc-bar"><i style="width:${Math.max(0, Math.min(100, pct)).toFixed(0)}%;background:${TONE[tone]}"></i></div>`;
  const metric = (label, value, unit, color, extra, sub) =>
    `<div class="mc-m"><span>${label}</span><b${color ? ` style="color:${color}"` : ''}>${value}${unit ? `<small>${unit}</small>` : ''}</b>${extra || ''}<em>${sub || ''}</em></div>`;
  // the chosen unit big (one decimal), the other one in the word line (°C with a decimal, °F whole)
  const tBig = has(r.t) ? fmtTemp(r.t, { digits: 1, bare: true }) : '—', tAlt = has(r.t) ? fmtTemp(r.t, { unit: otherUnit(), digits: otherUnit() === 'C' ? 1 : 0, tight: true }) : '';
  const other = (indoor ? state.outdoor : state.indoor) ? reading(indoor ? state.outdoor : state.indoor, !indoor) : {};
  // temperature in words, like CO₂ and humidity: a comfort range indoors, plain words outdoors (thresholds in °F, whatever the unit shown)
  const fT = has(r.t) ? toF(r.t) : null;
  const tl = !has(fT) ? { word: '', tone: 'muted' } : indoor
    ? (fT < 64 ? { word: 'Cold', tone: 'warn' } : fT < 68 ? { word: 'Cool', tone: 'muted' } : fT <= 76 ? { word: 'Comfortable', tone: 'muted' } : fT <= 80 ? { word: 'Warm', tone: 'muted' } : { word: 'Hot', tone: 'warn' })
    : { word: fT < 40 ? 'Cold' : fT < 60 ? 'Cool' : fT < 75 ? 'Mild' : fT < 85 ? 'Warm' : 'Hot', tone: 'muted' };
  return `<article class="card mc ${indoor ? 'mc-in' : 'mc-out'}" style="--tint:${indoor ? 'var(--series-in)' : 'var(--series-out)'}">
    <div class="mc-head">${uniq(indoor ? ICONS.sceneIn : ICONS.sceneOut).replace('<svg ', '<svg preserveAspectRatio="xMidYMax slice" ')}
      <div class="mc-id"><span class="mc-hw" aria-hidden="true">${uniq(indoor ? ICONS.one : ICONS.openair)}</span><div><div class="mc-kind ${indoor ? 'in' : 'out'}">${indoor ? 'Indoor' : 'Outdoor'}</div><div class="mc-name${pubName ? ' mc-pub' : ''}">${pubName ? esc(pubName) : indoor ? 'AirGradient ONE' : 'AirGradient Open Air'}<span class="mc-loc"> · ${what}</span></div><div class="mc-status ${f.tone}" title="${(m && m.timestamp ? 'Last reading ' + clock(m.timestamp) : 'No reading') + (has(wifi) ? ' · Wi‑Fi ' + wifi + ' dBm' : '')}"><i class="live ${f.tone}"></i><span class="mc-st">${f.label}<span class="mc-loc2" aria-hidden="true"> · ${what}</span>${has(wifi) && f.tone === 'good' ? `<span class="mc-wifi"> · Wi‑Fi ${wifi >= -65 ? 'good' : wifi >= -75 ? 'fair' : 'weak'}</span>` : ''}</span></div></div></div>
    </div>
    <div class="mc-hero ${pl.tone}">
      ${pmRing(r.pm, pl.tone)}
      <div><div class="mc-hero-k" style="color:${TONE[pl.tone]}">PM2.5 — ${pl.word}</div>
        <div class="mc-hero-s">Fine particles · aim under ${PM_FINE} µg/m³</div></div>
    </div>
    <div class="mc-grid">
      ${metric('CO₂', has(r.co2) ? Math.round(r.co2).toLocaleString() : '—', 'ppm', cl.tone === 'warn' || cl.tone === 'bad' ? TONE[cl.tone] : null, has(r.co2) ? bar(r.co2 / 2000 * 100, cl.tone === 'good' ? 'muted' : cl.tone) : '', cl.word)}
      ${metric('Temp', tBig, '°' + tempUnit(), tl.tone === 'warn' ? TONE.warn : null, has(r.t) ? tempScale(r.t, other.t, indoor) : '', has(r.t) ? `${tl.word} · ${tAlt}` : '')}
      ${metric('Humidity', has(r.rh) ? Math.round(r.rh) : '—', '%', indoor && hl.tone === 'warn' ? TONE.warn : null, has(r.rh) ? bar(r.rh, indoor && hl.tone === 'warn' ? 'warn' : 'muted') : '', hl.word)}
    </div>
    <div class="mc-pm mc-groups">
      <div class="mc-g"><span class="mc-gl">Gases</span><div class="mc-gr">
        <div title="Volatile organic compounds, Sensirion index (100 = this room's usual)"><span>VOC index</span><b${has(voc) && voc > 150 ? ' class="warn"' : ''}>${has(voc) ? voc : '—'}</b><em>${has(voc) ? (voc <= 100 ? 'normal' : voc <= 200 ? 'elevated' : 'high') : ''}</em></div>
        <div title="Nitrogen oxides, Sensirion index (1 = clean)"><span>NOx index</span><b>${has(nox) ? nox : '—'}</b><em>${has(nox) ? (nox <= 20 ? 'clean' : nox <= 100 ? 'moderate' : 'high') : ''}</em></div>
      </div></div>
      <div class="mc-g" title="Also measured: PM2.5 before AirGradient's correction ${pmNum(m && m.pm02)} µg/m³ · particles over 0.3 µm ${m && has(m.pm003Count) ? Math.round(m.pm003Count) : '—'} per dL"><span class="mc-gl">Particles</span><div class="mc-gr">
        <div><span>PM1</span><b>${pmNum(m && m.pm01)}<small>µg/m³</small></b></div>
        <div><span>PM10</span><b>${pmNum(pick(m, 'pm10_corrected', 'pm10'))}<small>µg/m³</small></b></div>
      </div></div>
    </div>${pubName ? `
    <p class="mc-credit">${monitorCredit(PUB, esc)}</p>` : ''}
  </article>`;
}

// The Monitor section: the home's two cards; a view without an indoor monitor shows the outdoor one first, then the slot.
function monitorsHTML() {
  return NO_INDOOR ? monitorCard(state.outdoor, false) + indoorSlotHTML() : monitorCard(state.indoor, true) + monitorCard(state.outdoor, false);
}

// Monitor status sits on the avatar as a dot; the words are its tooltip.
function updateStatus() {
  setTimeout(renderSources, 0);
  const live = monitorsLive([freshness(state.indoor, readingsNow(), NO_INDOOR), freshness(state.outdoor, readingsNow())]);
  monitorStatus('one', state.indoor); monitorStatus('openair', state.outdoor);
  const status = `${live.text} · ${sourceSummary()}`;
  $('avatar').dataset.tip = status; $('avatar').setAttribute('aria-label', 'Home · ' + status);
  $('dot-sum').className = 'av-dot ' + live.tone;
  const hw = $('vsum-hw');
  if (hw) hw.innerHTML = monitorPill(VIEW_PLACE, state.indoor, state.outdoor, readingsNow(), { one: uniq(ICONS.one), openair: uniq(ICONS.openair) });
}

function renderMonitors() {
  $('monitors').innerHTML = monitorsHTML();
  if (typeof SKY !== 'undefined' && SKY) SKY.pm(reading(state.outdoor, false).pm);
  updateStatus();
  const stamps = [state.indoor, state.outdoor].filter(m => m && m.timestamp).map(m => new Date(m.timestamp));
  lastStamp = stamps.length ? Math.max(...stamps) : null;
  loadFailed = false;
  showUpdated();
}

// ── Local conditions ──────────────────────────────────

// Production's content: a headline value, one line on what it is, then labeled details.
function kv(rows) {
  return rows.filter(Boolean).map(([k, v, tone]) => `<div><dt>${k}</dt><dd${tone ? ` class="${tone}"` : ''}>${v}</dd></div>`).join('');
}

// The home's usual pollen seasons (config: [month, day] dates), so the card can say what's in season and what's next.
// Live levels come from Google; these dates are the usual calendar, not a forecast.
const POLLEN_SEASONS = APP.pollen_seasons || [];
function renderPollenSeason(levels) {
  const box = $('pollen-season'); if (!box) return;
  box.innerHTML = pollenSeasonHTML(POLLEN_SEASONS, levels, new Date(appNow().toLocaleString('en-US', { timeZone: TZ })), APP.limits, APP.place.region, esc);
}

function setEdges() {
  for (const id of ['wx-hero', 'pollen-hero', 'bqe-hero', 'smoke-hero']) {
    const el = $(id), card = el && el.closest('.card');
    if (!card) continue;
    // the dot says whether the source is connected, as everywhere else on the page (the hero word's color says good or bad):
    // green when it answered, amber when it didn't (no data / not checked), none while loading
    // off or not set up is neither: no dot, a plain gray edge
    const t = el.textContent.trim(), failed = /^(No reading|No data|Not checked)$/.test(t), idle = /^(Off|Not set up)$/.test(t);
    const c = t === '—' || !t || idle ? '' : failed ? 'var(--warn-fill)' : 'var(--good)';
    card.style.setProperty('--edge', c || (idle ? 'var(--line-strong)' : 'var(--sky)'));
    card.classList.toggle('has-status', !!c);
    card.querySelector('.k-link')?.setAttribute('aria-description', failed ? 'Source not answering' : c ? 'Source connected' : 'Loading');
  }
}

function contextStatus(ctx) {
  const w = (ctx && ctx.weather) || {}, pollen = (ctx && ctx.pollen) || [], sm = (ctx && ctx.smoke) || {};
  setStatus('wx', has(w.temperature) ? 'good' : 'bad', has(w.temperature) ? 'Live' : 'No data', has(w.temperature) ? 'Current weather from Open-Meteo' : 'Open-Meteo did not answer');
  // Google returns every pollen type even out of season, so an empty list means no answer.
  const st = (ctx && ctx.status) || {};
  const offOf = id => sourceOff(id, st[id] || (SRC_ON[id] === false ? 'off' : ''), !!PUB);
  for (const id of ['pollen', 'smoke']) {
    const o = offOf(id);
    if (o) setStatus(id, 'neutral', o.word, o.line);
  }
  if (!offOf('pollen')) setStatus('pollen', pollen.length ? 'good' : 'bad', pollen.length ? 'Today' : 'No data', pollen.length ? "Today's pollen from Google" : 'Google Pollen did not answer');
  if (!offOf('smoke')) setStatus('smoke', sm.checked ? 'good' : 'bad', sm.checked ? `${sm.date ? new Date(sm.date + 'T12:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : 'Today'} map` : 'Not checked', sm.checked ? `NOAA smoke map${sm.date ? ' for ' + sm.date : ''}` : 'The NOAA smoke map did not load');
  if (SRC_ON.nearby === false || st.nearby === 'off') setStatus('nearby', 'neutral', 'Off', sourceOff('nearby', 'off').line);
  setStatus('bqe', 'neutral', 'Estimated', 'Calculated from the hour and the wind; nothing to connect');
  updateStatus();
}

// A source that is off or not set up: its card says so in the page's muted tone, with one line on what it adds.
// The card greys out (.card.off); pollen without a key keeps its season calendar (calendar: true), greyed too.
function idleCard(id, { word, line, calendar }) {
  $(id + '-hero').closest('.card').classList.add('off');
  $(id + '-hero').textContent = word;
  $(id + '-hero').style.setProperty('--c', 'var(--soft)');
  $(id + '-sub').textContent = line;
  $(id + '-kv').innerHTML = '';
  const season = $(id + '-season'); if (season) season.innerHTML = '';
  if (calendar) renderPollenSeason([]);   // the usual seasons, with no level for today
}

function renderContext(ctx) {
  state.ctx = ctx;   // kept so a unit switch can redraw without a reload
  const w = ctx.weather || {}, b = ctx.bqe || {}, pollen = ctx.pollen || [];
  window.__wx = w; window.__bqe = b; window.__road = ctx.road || null; window.__fc = Array.isArray(ctx.forecast) ? ctx.forecast : []; window.__pollenT = Array.isArray(ctx.pollen_tomorrow) ? ctx.pollen_tomorrow : [];
  if (state.neighbors && state.neighbors.length) renderNeighborhood();
  if (typeof SKY !== 'undefined' && SKY) SKY.weather(w);
  if (has(w.wind_speed)) {
    $('wx-hero').textContent = `${w.wind_cardinal} ${num(w.wind_speed)} km/h`;
    $('wx-sub').textContent = 'Wind direction and speed';
    const risk = String(w.dew_point_risk || '');
    const uv = has(w.uv_index) ? Math.round(w.uv_index) : null;
    $('wx-kv').innerHTML = kv([
      // the chosen unit first; °C with a decimal, °F whole
      has(w.temperature) && ['Temperature', [tempUnit(), otherUnit()].map(u => fmtTemp(w.temperature, { unit: u, digits: u === 'C' ? 1 : 0, tight: true })).join(' · ')],
      has(w.dew_point) && ['Dew point', `${fmtTemp(w.dew_point, { digits: tempUnit() === 'C' ? 1 : 0, tight: true })} · ${w.dew_point >= 16 ? 'humid' : w.dew_point >= 10 ? 'comfortable' : w.dew_point >= 5 ? 'dry' : 'very dry'}`, w.dew_point < 10 ? 'warn' : ''],
      has(w.dew_point) && ['Sinus dryness', w.dew_point < 5 ? 'High' : w.dew_point < 10 ? 'Some' : 'None', w.dew_point < 10 ? 'warn' : ''],
      has(w.visibility) && ['Visibility', `${num(w.visibility / 1000)} km`],
      uv != null && ['UV index', `${uv} · ${uv <= 2 ? 'Low' : uv <= 5 ? 'Moderate' : uv <= 7 ? 'High' : 'Very high'}`, uv <= 2 ? 'good' : 'warn'],
    ]);
  } else {
    $('wx-hero').textContent = 'No reading';
    $('wx-sub').textContent = 'Open-Meteo did not answer.';
    $('wx-kv').innerHTML = '';
  }

  const st = ctx.status || {}, pollenOff = sourceOff('pollen', st.pollen || (SRC_ON.pollen === false ? 'off' : ''), !!PUB);
  const smokeOff = sourceOff('smoke', st.smoke || (SRC_ON.smoke === false ? 'off' : ''), !!PUB);
  for (const id of ['pollen', 'smoke']) $(id + '-hero').closest('.card').classList.remove('off');   // idleCard greys it again if still off
  if (pollenOff) idleCard('pollen', pollenOff);
  else if (pollen.length) {
    const top = Math.max(...pollen.map(p => p.index || 0));
    const word = top === 0 ? 'None' : top <= 2 ? 'Low' : top === 3 ? 'Moderate' : 'High';
    $('pollen-hero').textContent = word;
    $('pollen-hero').style.setProperty('--c', pollenHigh(top, APP.limits) ? 'var(--warn)' : 'var(--good)');
    const offSeason = pollen.every(p => !p.in_season);
    $('pollen-sub').textContent = (top === 0 ? 'Nothing in the air today' : top <= 2 ? 'All allergens low' : 'Expect congestion outdoors') + (offSeason ? ' · all out of season' : '');
    // one row per type: its season across the year (with today), and today's level from Google
    $('pollen-kv').innerHTML = '';
    renderPollenSeason(pollen);
  } else {
    $('pollen-hero').textContent = 'No data';
    $('pollen-hero').style.setProperty('--c', 'var(--soft)');
    $('pollen-sub').textContent = 'Google Pollen did not answer.';
    $('pollen-kv').innerHTML = '';
  }

  $('bqe-hero').closest('.card').classList.remove('off');
  if (!APP.road && PUB) idleCard('bqe', sourceOff('road', 'off', true));   // a public monitor has no road: Off, greyed
  if (APP.road) {
    const t = String(b.traffic || '');
    const peak = t.startsWith('PEAK'), high = t.startsWith('HIGH'), rushName = (t.match(/^PEAK \((.+) rush\)/) || [])[1];
    $('bqe-hero').textContent = peak ? 'Peak' : high ? 'High' : 'Low';
    $('bqe-hero').style.setProperty('--c', peak || high ? 'var(--warn)' : 'var(--good)');
    $('bqe-sub').textContent = peak ? (rushName ? cap(rushName) + ' rush' : 'Rush hour') : high ? 'Rush shoulders' : 'Off-peak traffic';
    const pressure = b.pollution_pressure;
    $('bqe-kv').innerHTML = kv([
      has(pressure) && ['Pollution pressure', `${num(pressure)}×`, pressure > 1 ? 'warn' : 'good'],
      b.wind_impact && ['Wind', esc(b.wind_impact), ctx.road && ctx.road.toward ? 'warn' : ''],
      ...APP.road.rush.map(([a, e, name]) => [esc(cap(name)) + ' rush', hourRange(a, e, '–')]),
    ]);
    $('bqe-now').textContent = `Pressure is those two multiplied. Now, ${peak ? 'peak' : high ? 'high' : 'low'} traffic times ${has(w.wind_direction) ? 'a ' + w.wind_cardinal + ' wind' : 'an unknown wind'} is ${num(pressure)}.`;
  }

  const sm = ctx.smoke || {};
  const mapped = sm.date ? new Date(sm.date + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : null;
  if (smokeOff) {
    idleCard('smoke', smokeOff);
  } else if (!sm.checked) {
    $('smoke-hero').textContent = 'Not checked';
    $('smoke-hero').style.setProperty('--c', 'var(--soft)');
    $('smoke-sub').textContent = 'NOAA\u2019s smoke map did not load';
  } else {
    $('smoke-hero').textContent = sm.detected ? `${sm.density} smoke` : 'Not detected';
    $('smoke-hero').style.setProperty('--c', sm.detected ? (sm.density === 'Light' ? 'var(--warn)' : 'var(--bad)') : 'var(--good)');
    $('smoke-sub').textContent = sm.detected ? `Satellites mapped wildfire smoke over ${APP.place.name}` : `No wildfire smoke mapped over ${APP.place.name}`;
  }
  if (!smokeOff) $('smoke-kv').innerHTML = kv([mapped && ['Map date', mapped], ['Source', 'NOAA satellite smoke map']]);
  setEdges();
}

// ── Neighborhood ──────────────────────────────────────


// Neighborhood table rows highlight their dot on the map, and the other way around
document.addEventListener('mouseover', e => { const tr = e.target.closest && e.target.closest('#nb tr[data-id]'); if (tr && typeof NBMAP !== 'undefined') NBMAP.highlight(Number(tr.dataset.id)); });
document.addEventListener('mouseout', e => { const tr = e.target.closest && e.target.closest('#nb tr[data-id]'); if (tr && !tr.contains(e.relatedTarget) && typeof NBMAP !== 'undefined') NBMAP.highlight(null); });
$('nb-more') && $('nb-more').addEventListener('click', () => { state.nbAll = !state.nbAll; renderNeighborhood(); });
// A real neighbor's row opens in place (its chevron, or anywhere on the row); one row open at a time. Its ↗ opens the map.
$('nb') && $('nb').addEventListener('click', e => {
  if (e.target.closest('a')) return;
  const tr = e.target.closest('tr.nb-can'); if (!tr || !state.nb) return;
  const id = Number(tr.dataset.id), focused = !!(document.activeElement && document.activeElement.closest && document.activeElement.closest('#nb .nb-tgb'));
  state.nbOpen = state.nbOpen === id ? null : id;
  drawNbRows();
  if (focused) { const b = $('nb').querySelector(`tr[data-id="${id}"] .nb-tgb`); if (b) b.focus(); }   // the keyboard stays on the toggle
});

function growBars() {
  const table = document.querySelector('.nbt'); if (!table || reduceMotion.matches) return;
  const bars = [...table.querySelectorAll('.nbbar i')];
  bars.forEach(b => { b.style.transform = 'scaleX(0)'; });
  onVisible(table, () => bars.forEach((b, i) => { b.style.transform = '';
    b.animate([{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }], { duration: 800, delay: i * 35, easing: 'cubic-bezier(.2, .7, .2, 1)', fill: 'backwards' }); }));
}

function renderNeighborhood() {
  const own = new Set([state.indoor, state.outdoor].filter(Boolean).map(m => m.locationId));
  // each neighbor's PM2.5 is the corrected one when the server could correct it (nbPm, home.js), like the home's own monitors
  const live = state.neighbors.filter(n => !n.offline && has(nbPm(n)) && (!n.timestamp || readingsNow() - new Date(n.timestamp) < 2 * 3600e3));
  // the shown monitor's row reads what its outdoor card reads (nbYou, home.js)
  const you = nbYou(live.find(n => own.has(n.locationId)), state.outdoor, pick(state.outdoor, 'pm02_corrected', 'pm02'));
  const others = live.filter(n => !own.has(n.locationId));
  const rows = (you ? [you] : []).concat(others);
  setStatus('nearby', others.length ? 'good' : 'bad', others.length ? `${others.length} reporting` : 'No answer', others.length ? `${others.length} nearby monitors sent a reading in the last 2 hours` : 'Nearby monitors did not answer');
  if (!rows.length) {
    $('nb-lead').textContent = 'Nearby monitors did not answer.';
    $('nb').innerHTML = '';
    return;
  }
  // Speak only when the comparison changes a decision; otherwise stay silent.
  const lead = nbLead(you, others, PM_FINE, SELF, { esc, pm: pmNum, num });
  $('nb-lead').innerHTML = lead;
  $('nb-lead').hidden = !lead;
  $('nb-sub').textContent = `${others.length} public AirGradient monitors within 15 km · PM2.5 µg/m³`;
  const barMax = Math.max(55, Math.ceil(Math.max(...rows.map(nbPm))));
  const limPct = (PM_FINE / barMax * 100).toFixed(1);
  $('nb-max').textContent = barMax; $('nb-limpos').style.left = limPct + '%';
  $('nb-limpos').textContent = `${PM_FINE} limit`;
  $('nb-limpos').parentElement.parentElement.title = `PM2.5 scale in µg/m³; the tick marks the ${PM_FINE} limit`;
  const fmt = { esc, pm: pmNum, num, temp: v => fmtTemp(v, { tight: true }), when: ts => lastReadingText(ts, readingsNow(), TZ) };
  state.nb = { rows, you, scale: { limit: PM_FINE, high: PM_HIGH, barMax, limPct }, fmt };
  if (!rows.some(n => n.locationId === state.nbOpen)) state.nbOpen = null;   // the open monitor stopped reporting
  drawNbRows();
  if (!growBars.done) { growBars.done = true; growBars(); }   // once, when the table first fills
  // the map: same monitors, the road, and where the wind takes its exhaust
  const w = window.__wx || {}, road = APP.road;
  // what the map means for the block: toward comes from the server (/api/context road.toward); away is the arc opposite the road's
  const toward = !!(window.__road && window.__road.toward);
  const away = road && has(w.wind_direction) && bearingIn(w.wind_direction, road.toward.map(d => (d + 180) % 360));
  const ex = road ? `the ${esc(road.name)}'s traffic exhaust` : '';
  $('nb-wind').innerHTML = road && has(w.wind_direction) ? `<b>Wind ${esc(w.wind_cardinal || '')} ${num(w.wind_speed)} km/h:</b> ` + (
    toward ? `<b class="warn">${ex} drifts toward your block.</b> Worst in the rush hours; keep windows shut then.`
    : away ? `${ex} drifts away from your block.`
    : `${ex} passes beside your block, not over it.`) +
    ` <span class="nb-why">${esc(roadWhyText(road))}</span>` : '';
  if (typeof NBMAP !== 'undefined') NBMAP.update(you, others, has(w.wind_direction) ? w.wind_direction : null);
}

// The table's rows (the open one with its band), and the nearest 8 under the map with "Show all" for the rest.
function drawNbRows() {
  const { rows, you, scale, fmt } = state.nb;
  $('nb').innerHTML = rows.map(n => nbRowHTML(n, n === you, SELF, APP.place.name, scale, fmt, n.locationId === state.nbOpen)).join('');
  const more = $('nb-more'), extra = rows.length - 8;
  document.querySelector('.nb-card').classList.toggle('nb-all', !!state.nbAll);
  more.hidden = extra <= 0;
  more.innerHTML = state.nbAll ? 'Show the nearest 8 <svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="m18 15-6-6-6 6"/></svg>'
    : `Show ${extra} more monitor${extra === 1 ? '' : 's'} <svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>`;
  more.setAttribute('aria-expanded', String(!!state.nbAll));
  [...$('nb').querySelectorAll('tr[data-id]')].forEach((tr, i) => { tr.classList.toggle('nb-extra', i >= 8); });   // an open row's band hides with it (app.css)
}

// ── Charts ────────────────────────────────────────────

function bucket(rows, from, to, n, key) {
  const sums = new Array(n).fill(0), counts = new Array(n).fill(0);
  const span = to - from;
  for (const row of rows || []) {
    const v = key(row);
    if (!has(v)) continue;
    const i = Math.min(n - 1, Math.floor((new Date(row.timestamp) - from) / span * n));
    if (i < 0) continue;
    sums[i] += v; counts[i]++;
  }
  return sums.map((s, i) => counts[i] ? s / counts[i] : null);
}

function niceTicks(lo, hi) {
  const raw = (hi - lo) / 3, mag = Math.pow(10, Math.floor(Math.log10(raw || 1)));
  const step = [1, 2, 2.5, 5, 10].map(k => k * mag).find(k => k >= raw) || raw;
  const out = []; for (let t = Math.ceil(lo / step) * step; t <= hi + 1e-9; t += step) out.push(+t.toFixed(6));
  return out;
}

// Smooth path through points (monotone cubic, no overshoot below zero).
function smooth(pts) {
  if (pts.length < 2) return pts.length ? `M${pts[0][0]},${pts[0][1]}` : '';
  const n = pts.length, dx = [], m = [], t = [];
  for (let i = 0; i < n - 1; i++) { dx[i] = pts[i + 1][0] - pts[i][0]; m[i] = (pts[i + 1][1] - pts[i][1]) / dx[i]; }
  t[0] = m[0]; t[n - 1] = m[n - 2];
  for (let i = 1; i < n - 1; i++) t[i] = m[i - 1] * m[i] <= 0 ? 0 : 3 * (dx[i - 1] + dx[i]) / ((2 * dx[i] + dx[i - 1]) / m[i - 1] + (dx[i] + 2 * dx[i - 1]) / m[i]);
  let d = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
  for (let i = 0; i < n - 1; i++) {
    const h = dx[i] / 3;
    d += `C${(pts[i][0] + h).toFixed(1)},${(pts[i][1] + h * t[i]).toFixed(1)} ${(pts[i + 1][0] - h).toFixed(1)},${(pts[i + 1][1] - h * t[i + 1]).toFixed(1)} ${pts[i + 1][0].toFixed(1)},${pts[i + 1][1].toFixed(1)}`;
  }
  return d;
}

function draw(id, a, b, times, range, spec) {
  const svg = $(id);
  let last = a.length - 1; while (last > 0 && !has(a[last]) && !has(b[last])) last--;
  a = a.slice(0, last + 1); b = b.slice(0, last + 1); times = times.slice(0, last + 1);
  const W = 560, H = 210, L = 42, R = 72, T = 30, B = 24;   // R: room for the limit's label ("polluted ↑" is the longest)
  const iw = W - L - R, ih = H - T - B;
  const values = [...a, ...b].filter(has);
  if (!values.length) { svg.innerHTML = `<text x="${W / 2}" y="${H / 2}" text-anchor="middle">No readings in this range</text>`; return; }
  let lo = Math.min(...values), hi = Math.max(...values);
  // the limit is drawn when it's near the readings or under all of them (every reading over it); else "All under the limit"
  const limitNear = spec.limit <= hi * 1.35;
  if (limitNear) { hi = Math.max(hi, spec.limit); lo = Math.min(lo, spec.limit); }
  const pad = Math.max((hi - lo) * 0.1, spec.minSpan / 2);
  lo = Math.max(spec.floor, lo - pad); hi = hi + pad;
  const x = i => L + (a.length < 2 ? iw / 2 : i / (a.length - 1) * iw);
  const y = v => T + (1 - (v - lo) / (hi - lo)) * ih;
  const runs = ys => {           // continuous stretches of readings
    const out = []; let cur = [];
    ys.forEach((v, i) => { if (has(v)) cur.push([x(i), y(v)]); else if (cur.length) { out.push(cur); cur = []; } });
    if (cur.length) out.push(cur); return out;
  };
  const clip = id + '-over';
  // the part of a line over the limit is drawn again in amber, so entering the bad zone is visible
  const series = (ys, cls) => runs(ys).map(r => {
    const d = smooth(r);
    // area, then the over-the-limit shading (between the line and the limit, in amber), then the line in its own color on top
    return `<path d="${d}L${r[r.length - 1][0].toFixed(1)},${T + ih}L${r[0][0].toFixed(1)},${T + ih}Z" class="ts-area ${cls}"/>` +
      (limitNear ? `<path d="${d}L${r[r.length - 1][0].toFixed(1)},${y(spec.limit).toFixed(1)}L${r[0][0].toFixed(1)},${y(spec.limit).toFixed(1)}Z" class="ts-overfill" clip-path="url(#${clip})"/>` : '') +
      `<path d="${d}" class="ts-line ${cls}"/>`;
  }).join('');
  let g = limitNear ? `<defs><clipPath id="${clip}"><rect x="0" y="0" width="${W}" height="${y(spec.limit)}"/></clipPath></defs>` : '';
  niceTicks(lo, hi).forEach(t => {
    const yy = y(t).toFixed(1);
    g += `<line x1="${L}" y1="${yy}" x2="${L + iw}" y2="${yy}" class="ts-grid"/><text x="${L - 8}" y="${Number(yy) + 3.5}" text-anchor="end">${t.toLocaleString()}</text>`;
  });
  g += series(b, 'ts-out') + series(a, 'ts-in');
  if (limitNear) {
    const yy = y(spec.limit).toFixed(1);
    g += `<line x1="${L}" y1="${yy}" x2="${L + iw}" y2="${yy}" class="ts-guide"/>` +
      `<text class="ts-limword" x="${L + iw + 8}" y="${Number(yy) - 4}">${spec.word} ↑</text><text class="ts-limnum" x="${L + iw + 8}" y="${Number(yy) + 10}">${spec.limit.toLocaleString()}</text>`;
  }
  // legend, top right
  const over = limitNear && values.some(v => v > spec.limit), lx = over ? -112 : 0;
  g += `<g class="ts-legend" transform="translate(${L + iw + R - 4},12)">` + (NO_INDOOR ? '' : `<rect x="${-150 + lx}" y="-5" width="14" height="4" rx="2" class="ts-sw ts-in"/><text x="${-131 + lx}" y="0">Indoor</text>`) +
       `<rect x="${-76 + lx}" y="-5" width="14" height="4" rx="2" class="ts-sw ts-out"/><text x="${-57 + lx}" y="0">Outdoor</text>` +
       (over ? `<rect x="-100" y="-7" width="14" height="9" rx="2" class="ts-sw-over"/><text x="-81" y="0">Over the limit</text>` : '') + `</g>`;
  if (!limitNear) g += `<text class="ts-under" x="${L}" y="12">All under the limit of ${spec.limit.toLocaleString()}</text>`;
  // short axis labels that never collide: minutes for 1 h and 6 h, hours for 24 h, weekdays for 7 d
  const opt = range === '1h' || range === '6h' ? { timeZone: TZ, hour: 'numeric', minute: '2-digit' } : range === '24h' ? { timeZone: TZ, hour: 'numeric' } : { timeZone: TZ, weekday: 'short' };
  const ticks = 5;
  // evenly spaced along the axis (not by sample index, which bunches the last labels together)
  const t0 = +times[0], t1 = +times[times.length - 1];
  for (let k = 0; k <= ticks; k++) {
    const f = k / ticks;
    g += `<text x="${(L + f * iw).toFixed(1)}" y="${H - 6}" text-anchor="${k === 0 ? 'start' : k === ticks ? 'end' : 'middle'}">${new Date(t0 + f * (t1 - t0)).toLocaleString('en-US', opt)}</text>`;
  }
  g += `<g class="ts-hover" style="display:none"><line class="ts-xh" y1="${T}" y2="${T + ih}"/><circle class="ts-hd in" r="4"/><circle class="ts-hd out" r="4"/></g>`;
  svg.innerHTML = g;
  $(spec.noteId).textContent = RANGE_LABEL[range];
  svg.__hover = { kind: 'big', L, iw, x, y, a, b, times: times.map(Number), note: $(spec.noteId), label: RANGE_LABEL[range], spec };
  if (!reduceMotion.matches && svg.dataset.drawn !== range) {   // lines draw in when the range changes, once the chart is on screen
    svg.dataset.drawn = range;
    const lines = [...svg.querySelectorAll('.ts-line')], areas = [...svg.querySelectorAll('.ts-area')];
    lines.forEach(p => { const len = p.getTotalLength(); p.style.strokeDasharray = len; p.style.strokeDashoffset = len; });
    areas.forEach(p => { p.style.opacity = 0; });
    onVisible(svg, () => {
      lines.forEach(p => { const len = p.getTotalLength();
        p.animate([{ strokeDashoffset: `${len}` }, { strokeDashoffset: '0' }], { duration: 1400, easing: 'cubic-bezier(.65, 0, .35, 1)' })
          .finished.then(() => { p.style.strokeDasharray = ''; p.style.strokeDashoffset = ''; }, () => {}); p.style.strokeDashoffset = 0; });
      areas.forEach(p => { p.style.opacity = ''; const to = getComputedStyle(p).opacity;   // fade to the area's own light tint, not to solid
        p.animate([{ opacity: 0 }, { opacity: to }], { duration: 900, delay: 500, easing: 'ease-out', fill: 'backwards' }); });
    });
  }
  linkHover(svg);
}

// History is fetched once for 7 days, in the background; every shorter range is cut from it, so switching is instant.
// Until the week is in (or after it's 5 minutes old), the picked range is fetched on its own, with a loading state.
const hist = { week: null, at: 0, pending: null };
const fetchHist = (from, to) => Promise.all([state.indoor, state.outdoor].map(m =>
  m ? getJSON(`/api/history/${m.locationId}?from=${from.toISOString()}&to=${to.toISOString()}`).catch(() => null) : Promise.resolve([])));
// A public monitor's empty week isn't kept: the server answers [] when AirGradient's map is slow or down too, and a
// kept one would hide History for 30 minutes. The next loadCharts asks again.
function loadWeek() {   // once per visit, then at most every 30 minutes
  if (hist.pending) return hist.pending;
  if (hist.week && Date.now() - hist.at < 30 * 60e3) return Promise.resolve(hist.week);
  const to = readingsNow(), from = new Date(to - 168 * 3600e3);
  hist.pending = fetchHist(from, to).then(([ih, oh]) => {
    if (!ih || !oh || (PUB && !oh.length)) throw new Error('history');
    hist.week = { ih, oh, to }; hist.at = Date.now(); return hist.week;
  }).finally(() => { hist.pending = null; });
  return hist.pending;
}
function chartsLoading(on) {
  document.querySelector('.chart-bar').classList.toggle('loading', on);
  document.querySelectorAll('#chart-pm, #chart-co2').forEach(svg => svg.closest('.card').classList.toggle('loading', on));
}

// A public monitor's history is all or nothing (AirGradient's map has it or doesn't): its charts, or one line.
function showHistory(on) {
  $('hist-none').hidden = on;
  document.querySelector('.chart-bar').classList.toggle('none', !on);
  $('hist-charts').hidden = !on;
}

async function loadCharts({ fresh = false, quiet = false } = {}) {
  const range = state.range;
  // a public monitor's history is decided on the week (a quiet last hour isn't "no history"), fetched next to the range
  const weekP = PUB && !hist.week ? loadWeek().catch(() => {}) : null;
  document.querySelectorAll('#ranges button').forEach(btn => {
    const on = btn.dataset.range === range;
    btn.classList.toggle('on', on); btn.setAttribute('aria-checked', String(on));
  });
  // A range switch cuts from the saved week (instant); a refresh fetches only the range on screen.
  const week = !fresh && hist.week ? hist.week : null;
  const to = week ? week.to : readingsNow(), from = new Date(to - RANGE_HOURS[range] * 3600e3);
  let ih, oh;
  if (week) {
    const inRange = rows => (rows || []).filter(r => new Date(r.timestamp) >= from);
    ih = inRange(week.ih); oh = inRange(week.oh);
    if (Date.now() - hist.at > 5 * 60e3) setTimeout(() => { if (state.range === range) loadCharts({ fresh: true, quiet: true }); }, 0);   // then catch up on the newest readings
  } else {
    if (!quiet) chartsLoading(true);
    try { [ih, oh] = await fetchHist(from, to); } finally { if (range === state.range) chartsLoading(false); }
    loadWeek().catch(() => {});                     // the week for instant switching, once per visit
  }
  if (weekP) await weekP;
  if (range !== state.range) return;                // a newer range was picked meanwhile
  if (!ih || !oh) {                                 // a fetch failed: keep what's drawn rather than blanking it
    if ($('chart-co2').childElementCount) return;
    ih = ih || []; oh = oh || [];
  }
  const none = !!PUB && !oh.length && !(hist.week && hist.week.oh.length);
  showHistory(!none);
  if (none) return;
  const n = Math.min(96, Math.max(ih.length, oh.length, 2));
  const times = Array.from({ length: n }, (_, i) => new Date(+from + (i + 0.5) * (to - from) / n));
  const pm = row => pick(row, 'pm02_corrected', 'pm02');
  const co2 = row => pick(row, 'rco2_corrected', 'rco2');
  draw('chart-pm', bucket(ih, from, to, n, pm), bucket(oh, from, to, n, pm), times, range,
    { limit: PM_FINE, word: 'polluted', floor: 0, minSpan: 2, unit: 'µg/m³', noteId: 'pm-note', fmt: v => pmNum(v) });
  draw('chart-co2', bucket(ih, from, to, n, co2), bucket(oh, from, to, n, co2), times, range,
    { limit: CO2_OPEN, word: 'stale', floor: 0, minSpan: 100, unit: 'ppm', noteId: 'co2-note', fmt: v => Math.round(v).toLocaleString() });
  const rh = row => pick(row, 'rhum_corrected', 'rhum');
  draw('chart-rh', bucket(ih, from, to, n, rh), bucket(oh, from, to, n, rh), times, range,
    { limit: RH_DAMP, word: 'damp', floor: 0, minSpan: 10, unit: '%', noteId: 'rh-note', fmt: v => Math.round(v) + '%' });
}

// Run fn once when el is at least a third on screen (right away if it already is).
function onVisible(el, fn) {
  if (!el) return;
  if (!('IntersectionObserver' in window)) return fn();
  const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { io.disconnect(); fn(); } }, { threshold: .33 });
  io.observe(el);
}

// ── Linked hover: one moment, marked on every chart that covers it ──
const hoverCharts = new Set();
const atLabel = t => { const day = x => new Date(x).toLocaleDateString('en-US', { timeZone: TZ }), d = new Date(t);
  const pre = day(t) === day(readingsNow()) ? '' : day(t) === day(readingsNow() - 864e5) ? 'Yesterday ' : d.toLocaleDateString('en-US', { timeZone: TZ, weekday: 'short' }) + ' ';
  return pre + d.toLocaleTimeString('en-US', { timeZone: TZ, hour: 'numeric', minute: '2-digit' }); };
function linkHover(el) {
  hoverCharts.add(el);
  if (el.__wired) return; el.__wired = true;
  const at = e => { const h = el.__hover; if (!h) return null;
    const r = (h.kind === 'big' ? el : el.querySelector('svg')).getBoundingClientRect();
    if (h.kind === 'big') { const xs = (e.clientX - r.left) / r.width * 560, f = Math.min(1, Math.max(0, (xs - h.L) / h.iw)); return h.times[0] + f * (h.times[h.times.length - 1] - h.times[0]); }
    const f = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)); return h.t0 + f * (h.t1 - h.t0); };
  // mouse: hover shows the moment, leaving hides it. Touch: a tap shows it and it stays; dragging sideways scrubs;
  // tapping anywhere else hides it (see the document listener below).
  el.addEventListener('pointerdown', e => { if (e.pointerType !== 'mouse') broadcastHover(at(e)); });
  el.addEventListener('pointermove', e => { if (e.pointerType === 'mouse' || e.buttons || e.pressure) broadcastHover(at(e)); });
  el.addEventListener('pointerleave', e => { if (e.pointerType === 'mouse') broadcastHover(null); });
}
document.addEventListener('pointerdown', e => {
  if (e.pointerType !== 'mouse' && ![...hoverCharts].some(el => el.contains(e.target))) broadcastHover(null);
});
function broadcastHover(t) {
  for (const el of hoverCharts) {
    if (!el.isConnected) { hoverCharts.delete(el); continue; }
    const h = el.__hover; if (!h) continue;
    if (h.kind === 'big') {
      const g = el.querySelector('.ts-hover'), n = h.times.length;
      const inRange = t != null && t >= h.times[0] - 1 && t <= h.times[n - 1] + 1;
      if (!inRange) { g.style.display = 'none'; h.note.textContent = h.label; continue; }
      const i = Math.round((t - h.times[0]) / (h.times[n - 1] - h.times[0]) * (n - 1)), xx = h.x(i).toFixed(1);
      g.style.display = ''; g.querySelector('.ts-xh').setAttribute('x1', xx); g.querySelector('.ts-xh').setAttribute('x2', xx);
      for (const [cls, arr] of [['in', h.a], ['out', h.b]]) { const c = g.querySelector('.ts-hd.' + cls); if (has(arr[i])) { c.style.display = ''; c.setAttribute('cx', xx); c.setAttribute('cy', h.y(arr[i]).toFixed(1)); } else c.style.display = 'none'; }
      const f = v => has(v) ? h.spec.fmt(v) : '—';
      h.note.textContent = `${atLabel(h.times[i])} · ${NO_INDOOR ? '' : `Indoor ${f(h.a[i])} · `}Outdoor ${f(h.b[i])} ${h.spec.unit}`;
    } else {
      const inRange = t != null && t >= h.t0 && t <= h.t1;
      if (!inRange) { h.mark.style.display = 'none'; h.readout.textContent = h.label; h.readout.classList.remove('over'); continue; }
      const n = h.series.length, i = Math.min(n - 1, Math.max(0, Math.floor((t - h.t0) / (h.t1 - h.t0) * n))), v = h.series[i];
      const f = (i + .5) / n;
      h.mark.style.display = ''; h.mark.style.left = `calc((100% - var(--gut, 52px)) * ${f.toFixed(4)})`;
      const dot = h.mark.querySelector('i');
      if (has(v)) { dot.style.display = ''; dot.style.top = `${((1 - (v - h.lo) / (h.hi - h.lo)) * 100).toFixed(1)}%`; } else dot.style.display = 'none';
      const val = !has(v) ? 'no reading' : h.metric === 'pm' ? `${pmNum(v)} ${h.unit}` : `${Math.round(v).toLocaleString()} ${h.unit}`;
      // past a limit, the readout and the dot turn orange and say which side ("stale", "damp", "dry", "polluted")
      const past = !has(v) ? '' : h.metric === 'co2' ? (v > CO2_OPEN ? 'stale' : '') : h.metric === 'pm' ? (pmOver(v, PM_FINE) ? 'polluted' : '')
        : h.metric === 'humidity' ? (v > RH_DAMP ? 'damp' : v < RH_LOW ? 'dry' : '') : '';
      const when = atLabel(h.t0 + f * (h.t1 - h.t0)).replace(/^Yesterday (.+)$/, '$1 yest.');   // short, so the readout stays on the number's line
      h.readout.textContent = `${when} · ${val}${past ? ' · ' + past : ''}`;
      h.readout.classList.toggle('over', !!past); dot.classList.toggle('over', !!past);
    }
  }
}
function readPayload() {
  const i = reading(state.indoor, true), o = reading(state.outdoor, false);
  return {
    format: 'read',
    indoor_pm25: i.pm, indoor_co2: i.co2, indoor_humidity: i.rh, indoor_temp_c: i.t,
    outdoor_pm25: o.pm, outdoor_humidity: o.rh, outdoor_temp_c: o.t,
    indoor_location_id: state.indoor ? state.indoor.locationId : null,
    outdoor_location_id: state.outdoor ? state.outdoor.locationId : null
  };
}

function readKey(p) {
  const r = (v, s) => has(v) ? Math.round(v / s) : 'x';
  return [r(p.indoor_co2, 50), r(p.indoor_humidity, 3), r(p.outdoor_pm25, 1), homeHour()].join('|');
}

let revealNext = true;
function reveal() {   // a short fade on the summary's items as they arrive
  if (reduceMotion.matches) return;
  document.querySelectorAll('#summary .sx-row, #summary .sx-clear').forEach((el, i) => el.animate(
    [{ opacity: 0, transform: 'translateY(4px)' }, { opacity: 1, transform: 'none' }], { duration: 480, delay: i * 120, easing: 'cubic-bezier(.2, .7, .2, 1)', fill: 'backwards' }));
}

// the summary card: no TODAY label (the heading above has it); the need icons go in the card's header strip
const SUMMARY_OPTS = () => ({ label: false, needsEl: $('s-needs') });
const summaryPopOpen = () => !!document.querySelector('#summary details[open], #s-needs details[open]');

function renderRead(r, stale, why) {
  shownSig = readSig(r);
  // the card is drawn by static/summary.js from the rules' summary; an earlier read without one keeps what's shown
  if (r.summary) SummaryCard.renderSummary($('summary'), r.summary, appNow(), SUMMARY_OPTS());   // TODAY/TONIGHT is the heading above
  else if (!$('summary').childElementCount) SummaryCard.renderSummary($('summary'), null, appNow(), SUMMARY_OPTS());
  showUpdated();   // the heading follows the summary (Today / Tonight)
  if (revealNext) { revealNext = false; reveal(); }
  $('s-by').textContent = '';
  $('s-tag-t').textContent = 'Summary';
  if ($('s-ago')) { $('s-ago').dataset.at = Date.parse(r.generated_at) || +readingsNow(); agoTick(); }
  if ($('s-src')) $('s-src').dataset.when = r.clock ? `Written ${r.clock} ·\u00a0` : '';   // the banner's status line: when, then the sources
  const note = $('stale-note');
  note.hidden = !why;
  note.textContent = why === 'offline' ? `Earlier summary, written at ${r.clock}. It updates when the page is back online.`
    : why === 'failed' ? `Earlier summary, written at ${r.clock}. A new one could not be written just now.` : '';
  $('read-meta').textContent = `Updated at ${r.clock}${stale ? ' (earlier summary)' : ''}.`;
}

// ── Busy state ────────────────────────────────────────
// One counter so overlapping work (a manual refresh and the timer) shows one busy state.

const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const TURN_MS = 900;
let busyCount = 0, spin = null, lastStamp = null, loadFailed = false;

// The heading over the summary: Today or Tonight while the readings are fresh, otherwise when they are from.
const FRESH_MIN = 10;
function showUpdated() {
  const title = $('now-title'), meta = $('updated');
  const offline = navigator.onLine === false;
  const set = (t, m, stale) => {
    title.textContent = t; meta.textContent = busyCount ? '' : m;   // while busy, the button says Updating…
    title.classList.toggle('stale', stale); meta.classList.toggle('stale', stale && !busyCount);
  };
  // the heading over the summary: TODAY or TONIGHT (the card's span) while the readings are fresh
  const fresh = (state.read && state.read.summary && state.read.summary.label) || 'Today';
  if (lastStamp == null) return set(offline ? 'Offline' : fresh, loadFailed ? 'Readings did not load' : '', offline || loadFailed);
  const d = new Date(lastStamp);
  const day = t => new Date(t).toLocaleDateString('en-US', { timeZone: TZ });
  const at = day(d) === day(readingsNow()) ? clock(d)
    : d.toLocaleString('en-US', { timeZone: TZ, month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  const mins = Math.round((readingsNow() - lastStamp) / 60000);
  const age = mins < 60 ? `${mins} min old` : mins < 48 * 60 ? `${Math.round(mins / 60)} h old` : `${Math.round(mins / 1440)} days old`;
  if (offline) return set('Offline', `Last reading ${at}`, true);
  if (mins > FRESH_MIN) return set(`As of ${at}`, age, true);
  set(fresh, '', false);
}

function startSpin() {
  if (reduceMotion.matches) return;
  if (spin) { spin.effect.updateTiming({ iterations: Infinity }); return; }
  spin = $('read-refresh').querySelector('svg').animate(
    [{ transform: 'rotate(0turn)' }, { transform: 'rotate(1turn)' }],
    { duration: TURN_MS, iterations: Infinity, easing: 'linear' });
}

function stopSpin() {
  if (!spin) return;
  const a = spin;
  // Finish the turn in progress instead of snapping back to the start.
  a.effect.updateTiming({ iterations: Math.floor(a.currentTime / TURN_MS) + 1 });
  a.finished.then(() => { if (spin === a) spin = null; }, () => {});
}

// What the server is doing, shown right after the Refresh button at the real moments: reading the sources, then writing.
function setPhase(p) {
  const ai = document.querySelector('section.sum-card'), step = $('s-step'); if (!ai || !step) return;
  if (p) { ai.dataset.phase = p; step.textContent = p === 'read' ? 'Reading the monitors and sources…' : 'Writing the summary…'; }
  else { delete ai.dataset.phase; step.textContent = ''; }
}

function setBusy(on) {
  busyCount = Math.max(0, busyCount + (on ? 1 : -1));
  const busy = busyCount > 0;
  busyRipple(busy && manualBusy ? 'on' : 'off');   // the writing ripple only for a refresh the viewer asked for
  if (!busy) manualBusy = false;
  for (const el of [document.querySelector('section.sum-card'), $('read-refresh')]) el.setAttribute('aria-busy', String(busy));
  busy ? startSpin() : stopSpin();
  if (!busy) setPhase(null);
  const lbl = $('read-refresh').querySelector('span'); if (lbl) lbl.textContent = busy ? 'Updating…' : 'Refresh';
  showUpdated();
}

// A short fade on the parts that changed, so a new read is noticed without hiding the old one.
function settle(el, before) {
  if (!el || reduceMotion.matches || el.innerHTML === before) return;
  el.animate([{ opacity: .35 }, { opacity: 1 }], { duration: 420, easing: 'cubic-bezier(.2, .7, .2, 1)' });
}

// What the summary says, without the parts that change on every read (time).
const readSig = r => JSON.stringify({ ...r, generated_at: 0, clock: 0 });
let shownSig = null;

async function loadRead(force) {
  const payload = readPayload();
  const key = readKey(payload);
  if (!force && state.read && Date.now() - state.readAt < READ_MAX_AGE && key === state.readKey) return;
  setBusy(true);
  try {
    if (busyCount) setPhase('write');
    const r = await getJSON('/api/analyze', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...payload, force: !!force })
    });
    Object.assign(state, { read: r, readAt: Date.now(), readKey: key });
    store.set({ at: Date.now(), read: r });
    // nothing new to show: leave the page alone (no re-render, no fade). A manual refresh always shows its result.
    if (!revealNext && readSig(r) === shownSig) {   // redraw only so passed times drop ("before 4 PM"), unless a sentence is open
      if (r.summary && !summaryPopOpen()) SummaryCard.renderSummary($('summary'), r.summary, appNow(), SUMMARY_OPTS());
      return;
    }
    const parts = ['summary'].map(id => [$(id), $(id).innerHTML]);
    renderRead(r, false);
    parts.forEach(([el, before]) => settle(el, before));
  } catch (err) {
    console.error('read', err);
    const why = navigator.onLine === false ? 'offline' : 'failed';
    const saved = store.get();
    if (!state.read && saved && saved.read) renderRead(saved.read, true, why);
    else if (!state.read) $('summary').innerHTML = '<p class="sx-none">The summary didn’t load. Refresh to try again.</p>';
    else renderRead(state.read, true, why);
  } finally {
    setBusy(false);
  }
}

// ── Refresh ───────────────────────────────────────────

let inFlight = null, lastRefresh = 0;

// A config but no AirGradient token yet: the header and one plain card. Everything that needs the monitors stays hidden.
function showNoToken() {
  bootRead = null;
  document.body.classList.add('no-token');
  $('no-token').hidden = false;
  setBusy(false);
}

// manual: the person pressed refresh, so show the busy state from the first request and write a new read.
// busy: show the updating state without asking for a new summary (the first load)
function refresh({ manual = false, busy = false } = {}) {
  if (APP.state === 'no_token') { showNoToken(); return Promise.resolve(); }
  if (inFlight) return inFlight;
  const showBusy = manual || busy;
  if (manual) manualBusy = true;
  if (showBusy) setBusy(true);
  if (manual) revealNext = true;
  inFlight = (async () => {
    try {
      if (showBusy) setPhase('read');
      forceNext = manual;
      const nbP = SRC_ON.nearby === false ? Promise.resolve(null) : getJSON('/api/neighborhood').catch(() => null);   // the slowest source; the rest doesn't wait for it
      const [current, ctx] = await Promise.all([getJSON('/api/current'), getJSON('/api/context').catch(() => null)]);
      if (current && current.state === 'no_token') { showNoToken(); return; }
      state.indoor = current.find(m => m.locationType === 'indoor') || null;
      state.outdoor = current.find(m => m.locationType === 'outdoor') || null;
      renderMonitors();
      showBootRead();
      nbP.then(nb => { if (Array.isArray(nb)) { state.neighbors = nb; renderNeighborhood(); } });
      if (ctx) renderContext(ctx);
      contextStatus(ctx);
      await Promise.all([loadRead(manual), loadCharts({ fresh: true }), nbP]);
      forceNext = false;
    } catch (err) {
      console.error('refresh', err);
      loadFailed = true;
    } finally {
      forceNext = false;
      if (showBusy) setBusy(false);
      showUpdated();
      lastRefresh = Date.now();
      inFlight = null;
    }
  })();
  return inFlight;
}

$('ranges').addEventListener('click', e => {
  const btn = e.target.closest('button');
  if (btn) { state.range = btn.dataset.range; loadCharts(); }
});
$('read-refresh').addEventListener('click', () => refresh({ manual: true }));

// Show the last summary at once. Offline, any age will do; online, only a recent one.
const cached = store.get();
// The saved summary waits for the monitors' readings (usually < 0.5 s), so the whole card, CO₂ bars included,
// animates in together. At most 1.5 s; offline it shows at once.
let bootRead = null;
function showBootRead() {
  if (!bootRead) return;
  const c = bootRead; bootRead = null;
  Object.assign(state, { read: c.read, readAt: 0 });   // shown now; refreshed in the background
  renderRead(c.read, true, navigator.onLine === false ? 'offline' : undefined);
}
if (cached && cached.read && (navigator.onLine === false || Date.now() - cached.at < 30 * 60 * 1000)) {
  bootRead = cached;
  if (navigator.onLine === false) showBootRead(); else setTimeout(showBootRead, 1500);
}
refresh({ busy: true });   // the first load shows the updating state; the saved summary stays readable meanwhile
setInterval(() => { if (!document.hidden) refresh(); }, 60000);   // background tabs don't poll
document.addEventListener('visibilitychange', () => { if (!document.hidden && Date.now() - lastRefresh > 60000) refresh(); });
window.addEventListener('offline', showUpdated);
window.addEventListener('online', () => { showUpdated(); refresh(); });

// ── Theme ─────────────────────────────────────────────

const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');
// the summary's day chart is drawn to its width: redraw it when the width changes
let sxWidth = 0;
window.addEventListener('resize', () => { const sx = $('summary'); if (sx && sx.__redraw && sx.clientWidth !== sxWidth) { sxWidth = sx.clientWidth; sx.__redraw(); } });

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  document.querySelector('meta[name="theme-color"]').setAttribute('content', theme === 'dark' ? '#0b131c' : '#f4f6f8');
  let saved = null; try { saved = localStorage.getItem('aq-theme'); } catch {}
  document.querySelectorAll('[data-theme-pick]').forEach(b => {
    const on = b.dataset.themePick === (saved || 'system');
    b.classList.toggle('on', on); b.setAttribute('aria-checked', String(on));
  });
  const tb = $('theme-toggle'); if (tb) tb.setAttribute('aria-label', theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
  const sx = $('summary'); if (sx && sx.__redraw) sx.__redraw();   // the day chart reads its colours from the theme
  if (typeof SKY !== 'undefined' && SKY) SKY.theme();
  if (typeof NBMAP !== 'undefined') NBMAP.theme();
}
applyTheme(document.documentElement.getAttribute('data-theme') || 'light');
// A theme change is one cross-fade of the whole page. Per-element fades are switched off meanwhile,
// so the title, cards and sky can't change at different speeds.
function switchTheme(theme) {
  const root = document.documentElement;
  if (root.getAttribute('data-theme') === theme) { applyTheme(theme); return; }
  const swap = () => { root.classList.add('theme-swap'); applyTheme(theme); };
  const done = () => requestAnimationFrame(() => requestAnimationFrame(() => root.classList.remove('theme-swap')));
  if (document.startViewTransition && !reduceMotion.matches) document.startViewTransition(swap).finished.finally(done);
  else { swap(); done(); }
}
document.querySelectorAll('[data-theme-pick]').forEach(b => b.addEventListener('click', () => {
  const pick = b.dataset.themePick;
  try { pick === 'system' ? localStorage.removeItem('aq-theme') : localStorage.setItem('aq-theme', pick); } catch {}
  switchTheme(pick === 'system' ? (darkQuery.matches ? 'dark' : 'light') : pick);
}));
// Quick theme switch inside the weather pill (it sits in the menu's <summary>, so it must not open the menu)
$('theme-toggle').addEventListener('click', e => {
  e.preventDefault(); e.stopPropagation();
  const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  try { localStorage.setItem('aq-theme', next); } catch {}
  switchTheme(next);
});
// Follow the system until the viewer picks a theme.
darkQuery.addEventListener('change', e => {
  let saved = null;
  try { saved = localStorage.getItem('aq-theme'); } catch {}
  if (!saved) switchTheme(e.matches ? 'dark' : 'light');
});

// ── Temperature unit ──────────────────────────────────

// °C or °F, from the Weather & theme menu. Saved in this browser; switching redraws every temperature without a reload.
function syncTempSeg() {
  document.querySelectorAll('[data-temp-unit]').forEach(b => {
    const on = b.dataset.tempUnit === tempUnit();
    b.classList.toggle('on', on); b.setAttribute('aria-checked', String(on)); b.tabIndex = on ? 0 : -1;
  });
}
function setTempUnit(u) {
  if (u !== 'C' && u !== 'F') return;
  try { u === 'C' ? localStorage.removeItem(TEMP_KEY) : localStorage.setItem(TEMP_KEY, u); } catch {}
  const changed = u !== tempPref;
  tempPref = u; syncTempSeg();
  if (!changed) return;
  if (state.indoor || state.outdoor) $('monitors').innerHTML = monitorsHTML();
  if (state.ctx) renderContext(state.ctx);   // the weather card and the neighborhood table
  else if (state.neighbors.length) renderNeighborhood();
  if (typeof SKY !== 'undefined' && SKY) SKY.units();   // the weather line in the header
}
document.querySelectorAll('[data-temp-unit]').forEach(b => {
  b.addEventListener('click', () => setTempUnit(b.dataset.tempUnit));
  // a radio group: the arrow keys move the choice, Tab leaves the group
  b.addEventListener('keydown', e => {
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) return;
    e.preventDefault();
    const next = b.dataset.tempUnit === 'C' ? 'F' : 'C';
    setTempUnit(next);
    document.querySelector(`[data-temp-unit="${next}"]`).focus();
  });
});
syncTempSeg();

// ── Install and offline ───────────────────────────────

if ('serviceWorker' in navigator) {
  const local = ['localhost', '127.0.0.1'].includes(location.hostname);
  if (local) {
    // Local development: drop any old worker so edits show up on refresh.
    navigator.serviceWorker.getRegistrations().then(regs => regs.forEach(r => r.unregister()));
  } else {
    navigator.serviceWorker.register('/sw.js').then(reg => setInterval(() => reg.update(), 60 * 60 * 1000))
      .catch(err => console.error('Service worker registration failed:', err));
  }
}

// Saved-view popover: standard dropdown behavior.
(() => {
  const view = document.querySelector('.bar details.custom');
  if (!view) return;
  const trigger = view.querySelector('summary');
  const sync = () => trigger.setAttribute('aria-expanded', String(view.open));
  const close = (refocus) => { if (!view.open) return; view.open = false; sync(); if (refocus) trigger.focus(); };
  view.addEventListener('toggle', sync); sync();
  $('view-close').addEventListener('click', e => { e.preventDefault(); close(true); });
  document.addEventListener('click', e => { if (view.open && !view.contains(e.target)) close(false); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && view.open) close(true); });
})();

// The summary byline shows its sources as a small stack of the Home panel's icons: gray at rest, in color and fanned out on hover,
// with a dot on any source that isn't answering, and a card listing each source with its live status.
const SOURCES = [['AirGradient ONE', 'one', 'Your indoor monitor'], ['AirGradient Open Air', 'openair', PUB ? 'This monitor' : 'Your outdoor monitor'],
  ['Open-Meteo', 'wx', 'Weather · Open-Meteo'], ['Google Pollen', 'pollen', 'Pollen · Google'], ['NOAA HMS', 'smoke', 'Smoke · NOAA'],
  ...(APP.road ? [[`${APP.road.name} estimate`, 'bqe', `Traffic · ${APP.road.name} estimate`]] : [])]
  .filter(([, id]) => sourcesOn(APP.sources, !!APP.road, !NO_INDOOR).includes(id));   // what the config turned off is not listed or counted
function renderSources() {
  const box = $('s-src'); if (!box) return;
  const rows = [...document.querySelectorAll('.blocks .pr')];
  const icon = name => { const li = rows.find(r => { const b = r.querySelector('.pr-t b'); return b && b.textContent === name; }); return li ? li.querySelector('.pr-ic').innerHTML : ''; };
  const st = id => { const el = $('st-' + id); return el ? { tone: (el.className.match(/\b(good|warn|bad|neutral)\b/) || [])[1] || '', text: el.textContent.trim() } : { tone: '', text: '' }; };
  // the byline says how many sources, and how many aren't answering; the card on hover lists them
  const down = SOURCES.filter(([, id]) => /warn|bad/.test(st(id).tone)).length;
  box.innerHTML = `<span class="s-src-n">from ${SOURCES.length} sources${down ? `<em> · ${down} not answering</em>` : ''}</span>`;
  const list = $('s-src-list');
  if (list) list.innerHTML = SOURCES.map(([name, id, label]) => { const x = st(id);
    return `<span class="s-src-row"><span class="s-src-ic">${icon(name)}</span><span>${esc(label)}</span><em class="${x.tone}">${esc(x.text || '…')}</em></span>`; }).join('');
}
renderSources();

// Links from the advice into the Home panel: a card's need opens it at "Specific needs", the byline's sources at the sources.
function openHome(where) {
  const home = document.querySelector('.bar details.custom'), dsp = $('dsp'); if (!home) return;
  if (dsp) dsp.open = false;
  home.open = true;
  window.scrollTo({ top: 0, behavior: reduceMotion.matches ? 'auto' : 'smooth' });
  const heads = [...home.querySelectorAll('.blocks section.pg h4')];
  const targets = where === 'needs' ? heads.filter(h => /needs/i.test(h.textContent)) : heads.filter(h => /monitors|outside/i.test(h.textContent));
  targets.forEach(h => { const sec = h.closest('section');
    if (!reduceMotion.matches) sec.animate([{ backgroundColor: 'var(--accent-soft)' }, { backgroundColor: 'transparent' }], { duration: 1600, delay: 250, easing: 'ease-out' }); });
}
document.addEventListener('click', e => {
  const t = e.target.closest('[data-open-home]'); if (!t) return;
  e.preventDefault(); e.stopPropagation(); openHome(t.dataset.openHome);
}, true);
$('s-src') && $('s-src').addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openHome('sources'); } });

// Dev and local only: the build and a Clear cache button (the dev site registers a service worker that caches files).
(() => {
  if (!(APP.env === 'dev' || APP.env === 'preview') || /[?&]shot\b/.test(location.search)) return;   // only dev and preview, never in screenshots
  const bar = $('devbar'); if (!bar) return;
  $('build').textContent = document.body.dataset.build || 'local';
  bar.hidden = false;
  $('clear-cache').addEventListener('click', async () => {
    $('clear-cache').textContent = 'Clearing…';
    try {
      if ('serviceWorker' in navigator) for (const r of await navigator.serviceWorker.getRegistrations()) await r.unregister();
      if ('caches' in window) await Promise.all((await caches.keys()).map(k => caches.delete(k)));
      try { localStorage.removeItem(CACHE_KEY); } catch {}
    } finally { location.reload(); }
  });
})();

// The address opens the map; it must not also toggle the Home panel.
document.querySelectorAll('a.addr').forEach(a => a.addEventListener('click', e => e.stopPropagation()));

// Pin the weather panel where it opened (see app.css): measured once on open, relative to the "Right now" line
(() => { const d = document.getElementById('dsp'); if (!d) return;
  d.addEventListener('toggle', () => { if (!d.open) return; const line = d.closest('.now-line'); if (!line) return;
    const x = d.getBoundingClientRect().left - line.getBoundingClientRect().left - 6;
    line.style.setProperty('--pop-left', Math.max(0, Math.round(x)) + 'px'); });
})();

// Weather view: the page fades away except the "Right now" row (its weather and theme menu stays usable), so the sky fills the page.
// The bottom bar offers the browser's full screen as an option, and "Show the page"; Esc also leaves. Not remembered.
(() => { const open = document.getElementById('fx-full'), box = document.getElementById('wx-mode'), exit = document.getElementById('wx-exit'), fs = document.getElementById('wx-fs');
  if (!open || !box) return;
  const R = document.documentElement;
  const leave = () => { if (!R.classList.contains('wx-full')) return; R.classList.remove('wx-full'); box.hidden = true; label(false);
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {}); };
  const label = on => { const t = [...open.childNodes].find(n => n.nodeType === 3); if (t) t.textContent = on ? 'Close weather view' : 'Open weather view'; };
  open.addEventListener('click', () => { if (R.classList.contains('wx-full')) return leave();
    R.classList.add('wx-full'); box.hidden = false; label(true);
    // the controls stay open, docked, on the previews, so the sky is visible while you play
    const d = document.getElementById('dsp'); if (d) { d.open = true; const pv = d.querySelector('.fx-preview'); if (pv) pv.open = true; } });
  exit.addEventListener('click', leave);
  if (fs) { if (!R.requestFullscreen) fs.hidden = true;
    fs.addEventListener('click', () => { if (document.fullscreenElement) document.exitFullscreen().catch(() => {}); else R.requestFullscreen().catch(() => {}); });
    document.addEventListener('fullscreenchange', () => { const on = !!document.fullscreenElement; fs.setAttribute('aria-pressed', on); fs.title = on ? 'Exit full screen' : 'Full screen'; fs.setAttribute('aria-label', fs.title); }); }
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !document.getElementById('dsp')?.open && !document.fullscreenElement) leave(); });
})();

// Weather menu: mark the chosen preview preset, and paint each slider's filled track (--p)
(() => { const pop = document.querySelector('.dsp-pop'); if (!pop) return;
  const presets = [...pop.querySelectorAll('[data-fx]')], live = document.getElementById('fx-live');
  const mark = b => presets.forEach(x => x.setAttribute('aria-pressed', String(x === b)));
  presets.forEach(b => b.addEventListener('click', () => mark(b)));
  if (live) live.addEventListener('click', () => mark(null));
  const ranges = [...pop.querySelectorAll('input[type=range]')];
  const fill = () => ranges.forEach(r => r.style.setProperty('--p', ((r.value - r.min) / (r.max - r.min) * 100).toFixed(1) + '%'));
  ranges.forEach(r => r.addEventListener('input', () => { fill(); mark(null); }));
  new MutationObserver(fill).observe(pop, { subtree: true, childList: true, characterData: true });
  fill(); mark(null);
})();

// Banner: "Updated 5 min ago" (relative, so it never clashes with the clock in Right now), refreshed every 30 s.
function agoTick() { const el = document.getElementById('s-ago'); if (!el || !el.dataset.at) return;
  const m = Math.round((readingsNow() - Number(el.dataset.at)) / 60000);
  el.textContent = m < 1 ? 'Updated just now' : m < 60 ? `Updated ${m} min ago` : `Updated ${Math.round(m / 60)} h ago`; }
setInterval(agoTick, 30000);

// The AI dot's ripple: rings spread from it when a fresh summary lands (once), and keep spreading while it's writing.
// Event-driven on purpose: the only continuous pulse on the page is the green "live" dot.
var rippleTimer = null, manualBusy = false;   // var: setBusy can call busyRipple during startup, before this line runs
function busyRipple(mode) {
  const rings = [...document.querySelectorAll('.s-busy-mark .rip')]; if (!rings.length || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const wave = () => rings.forEach((c, k) => setTimeout(() => c.querySelectorAll('animate').forEach(a => { try { a.beginElement(); } catch (e) {} }), k * 300));
  if (mode === 'once') { if (!rippleTimer) wave(); return; }
  if (mode === 'on') { if (!rippleTimer) { wave(); rippleTimer = setInterval(wave, 1900); } return; }
  clearInterval(rippleTimer); rippleTimer = null;
}

// Preview menu: "Random" cycles through random moments, a new one every 8 s (long enough for the sky to ease into it).
// It stops on a preset, a slider, Back to live, or a second click.
(() => { const b = document.getElementById('fx-rand'); if (!b) return;
  const CYCLE_MS = 8000; let t = null;
  const r = (a, z, step = 1) => Math.round((a + Math.random() * (z - a)) / step) * step;
  const pick = () => { const rain = Math.random() < .3 ? r(20, 100) / 100 : 0;
    return { minutes: r(0, 1435, 5), dir: r(0, 359), spd: r(0, 38, .5), cloud: rain ? r(60, 100) : r(0, 90), rain, thunder: rain > .85,
      pm: Math.random() < .15 ? r(35, 70, .5) : r(0, 18, .5) }; };
  const stop = () => { clearInterval(t); t = null; b.setAttribute('aria-pressed', 'false'); };
  const step = () => window.skyPreview && window.skyPreview(pick());
  b.addEventListener('click', () => { if (t) return stop();
    document.querySelectorAll('.fx-presets [data-fx]').forEach(x => x.setAttribute('aria-pressed', 'false'));
    b.setAttribute('aria-pressed', 'true'); step(); t = setInterval(step, CYCLE_MS); });
  document.querySelectorAll('.fx-presets [data-fx], #fx-live').forEach(x => x.addEventListener('click', stop));
  document.querySelectorAll('.fx-sliders input').forEach(x => x.addEventListener('input', e => { if (e.isTrusted) stop(); }));
})();
