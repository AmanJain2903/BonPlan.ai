import axios from 'axios';
import { API_BASE, FALLBACK_IMAGE } from './config';

export const api = {
    getDestinationImage: async (destination: string): Promise<string> => {
        try {
            const { data } = await axios.get<{ image_url: string }>(
                `${API_BASE}/api/v1/places/destination-image`,
                { params: { destination } }
            );
            return data.image_url;
        } catch (error) {
            console.error('Failed to fetch destination image:', error);
            // Fallback image in case of error (a nice default placeholder)
            return FALLBACK_IMAGE;
        }
    },

    getDestinationImages: async (destination: string, count: number = 10, min_ratio: number = 1.4): Promise<string[]> => {
        try {
            const { data } = await axios.get<{ image_urls: string[] }>(
                `${API_BASE}/api/v1/places/destination-images`,
                { params: { destination, count, min_ratio } }
            );
            return data.image_urls;
        } catch (error) {
            console.error('Failed to fetch destination image:', error);
            // Fallback image in case of error (a nice default placeholder)
            return [FALLBACK_IMAGE];
        }
    }
};
