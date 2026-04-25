export const airports = [
    // --- NORTH AMERICA ---
    { code: 'JFK', lat: 40.64, lng: -73.78 }, // New York
    { code: 'LAX', lat: 33.94, lng: -118.41 }, // Los Angeles
    { code: 'ORD', lat: 41.97, lng: -87.91 }, // Chicago
    { code: 'MIA', lat: 25.80, lng: -80.29 }, // Miami
    { code: 'SFO', lat: 37.62, lng: -122.38 }, // San Francisco
    { code: 'ATL', lat: 33.64, lng: -84.42 }, // Atlanta
    { code: 'DFW', lat: 32.89, lng: -97.04 }, // Dallas
    { code: 'DEN', lat: 39.85, lng: -104.67 }, // Denver
    { code: 'SEA', lat: 47.45, lng: -122.30 }, // Seattle
    { code: 'LAS', lat: 36.08, lng: -115.15 }, // Las Vegas
    { code: 'EWR', lat: 40.69, lng: -74.16 }, // Newark
    { code: 'BOS', lat: 42.36, lng: -71.00 }, // Boston
    { code: 'IAD', lat: 38.95, lng: -77.45 }, // Washington Dulles
    { code: 'YYZ', lat: 43.68, lng: -79.63 }, // Toronto
    { code: 'YVR', lat: 49.19, lng: -123.18 }, // Vancouver
    { code: 'YUL', lat: 45.47, lng: -73.74 }, // Montreal
    { code: 'MEX', lat: 19.43, lng: -99.07 }, // Mexico City
    { code: 'CUN', lat: 21.03, lng: -86.87 }, // Cancun
  
    // --- SOUTH & CENTRAL AMERICA ---
    { code: 'GRU', lat: -23.44, lng: -46.47 }, // Sao Paulo
    { code: 'GIG', lat: -22.81, lng: -43.25 }, // Rio de Janeiro
    { code: 'EZE', lat: -34.82, lng: -58.54 }, // Buenos Aires
    { code: 'SCL', lat: -33.39, lng: -70.79 }, // Santiago
    { code: 'BOG', lat: 4.70, lng: -74.14 }, // Bogota
    { code: 'LIM', lat: -12.02, lng: -77.11 }, // Lima
    { code: 'PTY', lat: 9.07, lng: -79.38 }, // Panama City
    { code: 'BSB', lat: -15.86, lng: -47.92 }, // Brasilia
    { code: 'UIO', lat: -0.12, lng: -78.35 }, // Quito
  
    // --- EUROPE ---
    { code: 'LHR', lat: 51.47, lng: -0.45 }, // London Heathrow
    { code: 'CDG', lat: 49.01, lng: 2.55 },  // Paris
    { code: 'FRA', lat: 50.04, lng: 8.56 },  // Frankfurt
    { code: 'AMS', lat: 52.31, lng: 4.77 },  // Amsterdam
    { code: 'MAD', lat: 40.50, lng: -3.57 }, // Madrid
    { code: 'FCO', lat: 41.80, lng: 12.24 }, // Rome
    { code: 'MUC', lat: 48.35, lng: 11.78 }, // Munich
    { code: 'ZRH', lat: 47.46, lng: 8.54 },  // Zurich
    { code: 'LIS', lat: 38.77, lng: -9.13 }, // Lisbon
    { code: 'BCN', lat: 41.29, lng: 2.07 },  // Barcelona
    { code: 'ATH', lat: 37.93, lng: 23.94 }, // Athens
    { code: 'DUB', lat: 53.42, lng: -6.24 }, // Dublin
    { code: 'CPH', lat: 55.61, lng: 12.65 }, // Copenhagen
    { code: 'OSL', lat: 60.19, lng: 11.10 }, // Oslo
    { code: 'ARN', lat: 59.65, lng: 17.91 }, // Stockholm
    { code: 'HEL', lat: 60.31, lng: 24.96 }, // Helsinki
    { code: 'WAW', lat: 52.16, lng: 20.96 }, // Warsaw
    { code: 'VIE', lat: 48.11, lng: 16.56 }, // Vienna
    { code: 'IST', lat: 41.28, lng: 28.75 }, // Istanbul
  
    // --- MIDDLE EAST ---
    { code: 'DXB', lat: 25.25, lng: 55.37 }, // Dubai
    { code: 'DOH', lat: 25.26, lng: 51.61 }, // Doha
    { code: 'AUH', lat: 24.43, lng: 54.65 }, // Abu Dhabi
    { code: 'RUH', lat: 24.95, lng: 46.69 }, // Riyadh
    { code: 'JED', lat: 21.67, lng: 39.15 }, // Jeddah
    { code: 'MCT', lat: 23.59, lng: 58.28 }, // Muscat
    { code: 'AMM', lat: 31.72, lng: 35.99 }, // Amman
    { code: 'TLV', lat: 32.00, lng: 34.88 }, // Tel Aviv
  
    // --- ASIA ---
    { code: 'HND', lat: 35.55, lng: 139.77 }, // Tokyo Haneda
    { code: 'NRT', lat: 35.77, lng: 140.39 }, // Tokyo Narita
    { code: 'ICN', lat: 37.46, lng: 126.44 }, // Seoul
    { code: 'PEK', lat: 40.08, lng: 116.60 }, // Beijing
    { code: 'PVG', lat: 31.14, lng: 121.80 }, // Shanghai
    { code: 'CAN', lat: 23.39, lng: 113.29 }, // Guangzhou
    { code: 'HKG', lat: 22.31, lng: 113.92 }, // Hong Kong
    { code: 'TPE', lat: 25.07, lng: 121.23 }, // Taipei
    { code: 'BKK', lat: 13.69, lng: 100.75 }, // Bangkok
    { code: 'SIN', lat: 1.36, lng: 103.99 },  // Singapore
    { code: 'KUL', lat: 2.74, lng: 101.69 },  // Kuala Lumpur
    { code: 'CGK', lat: -6.12, lng: 106.65 }, // Jakarta
    { code: 'MNL', lat: 14.50, lng: 121.01 }, // Manila
    { code: 'SGN', lat: 10.81, lng: 106.66 }, // Ho Chi Minh City
    { code: 'DEL', lat: 28.56, lng: 77.10 },  // Delhi
    { code: 'BOM', lat: 19.09, lng: 72.87 },  // Mumbai
    { code: 'BLR', lat: 13.19, lng: 77.70 },  // Bangalore
    { code: 'MAA', lat: 12.99, lng: 80.17 },  // Chennai
    { code: 'HYD', lat: 17.24, lng: 78.42 },  // Hyderabad
  
    // --- AFRICA ---
    { code: 'JNB', lat: -26.14, lng: 28.25 }, // Johannesburg
    { code: 'CPT', lat: -33.97, lng: 18.60 }, // Cape Town
    { code: 'NBO', lat: -1.32, lng: 36.93 },  // Nairobi
    { code: 'ADD', lat: 8.98, lng: 38.80 },   // Addis Ababa
    { code: 'CAI', lat: 30.12, lng: 31.41 },  // Cairo
    { code: 'LOS', lat: 6.57, lng: 3.32 },    // Lagos
    { code: 'CMN', lat: 33.36, lng: -7.58 },  // Casablanca
    { code: 'ALG', lat: 36.69, lng: 3.21 },   // Algiers
    { code: 'DKR', lat: 14.67, lng: -17.07 }, // Dakar
    { code: 'ACC', lat: 5.60, lng: -0.16 },   // Accra
  
    // --- OCEANIA ---
    { code: 'SYD', lat: -33.95, lng: 151.18 }, // Sydney
    { code: 'MEL', lat: -37.67, lng: 144.84 }, // Melbourne
    { code: 'BNE', lat: -27.38, lng: 153.11 }, // Brisbane
    { code: 'PER', lat: -31.94, lng: 115.96 }, // Perth
    { code: 'AKL', lat: -37.00, lng: 174.79 }, // Auckland
    { code: 'CHC', lat: -43.48, lng: 172.53 }, // Christchurch
    { code: 'NAN', lat: -17.75, lng: 177.44 }, // Nadi (Fiji)
  ];