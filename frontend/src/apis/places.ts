import axios from 'axios';
import { API_BASE } from './config';

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
            return 'https://images.unsplash.com/photo-1488646953014-c8cb19dc014a?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80';
        }
    }
};
