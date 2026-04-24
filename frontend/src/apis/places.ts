import axios from 'axios';
import { API_BASE, FALLBACK_IMAGE } from './config';

export const api = {
    getDestinationImagesByName: async (destination: string, count: number = 10, min_ratio: number = 1.5): Promise<string[]> => {
        try {
            const { data } = await axios.get<{ image_urls: string[] }>(
                `${API_BASE}/api/v1/places/destination-images-by-name`,
                { params: { destination, count, min_ratio } }
            );
            console.log('Destination images by name:', data);
            return data.image_urls;
        } catch (error) {
            console.error('Failed to fetch destination image:', error);
            // Fallback image in case of error (a nice default placeholder)
            return [FALLBACK_IMAGE];
        }
    },
    getDestinationImagesByPlaceId: async (place_id: string, count: number = 10, min_ratio: number = 1.5): Promise<string[]> => {
        try {
            const { data } = await axios.get<{ image_urls: string[] }>(`${API_BASE}/api/v1/places/destination-image-by-place-id`, {
                params: { place_id, count, min_ratio }
            });
            return data.image_urls;
        } catch (error) {
            console.error('Failed to fetch destination image:', error);
            return [FALLBACK_IMAGE];
        }
    },
};
