<script lang="ts">
import { defineComponent } from 'vue';
import { useStore } from '../store/types';

export default defineComponent({
  name: 'ShareTabs',
  props: {
    value: {
      type: Number,
      required: true,
    },
  },
  setup() {
    const store = useStore();
    const locationStore = store.state.Location;
    const { getters } = store;

    const clearSelected = () => {
      store.commit('Location/setSelected', []);
    };

    return {
      locationStore,
      getters,
      clearSelected,
    };
  },
});
</script>

<template>
  <div>
    <v-tabs
      grow
      class="px-0"
      @change="clearSelected"
    >
      <v-tab :to="{ name: 'shared-with-all' }">
        Find Data
      </v-tab>
      <v-tab :to="{ name: 'shared-with-me' }">
        Shared with me
      </v-tab>
      <v-tab :to="{ name: 'requests' }">
        Pending requests
      </v-tab>
    </v-tabs>
    <router-view />
  </div>
</template>

<style scoped>
.tab-icon {
  width: 28px;
  margin-right: 10px;
}
</style>
